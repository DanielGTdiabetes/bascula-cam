sudo install -d -m 755 /opt/bascula/current/scripts

sudo tee /opt/bascula/current/scripts/safe_run.sh >/dev/null <<'SH'
#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

APP_DIR="${APP_DIR:-/opt/bascula/current}"
PY="$APP_DIR/.venv/bin/python3"
# Flags de recuperación
PERSIST_RECOVERY_FLAG="/opt/bascula/shared/userdata/force_recovery"
TEMP_RECOVERY_FLAG="/tmp/bascula_force_recovery"
BOOT_RECOVERY_FLAG="/boot/bascula-recovery"

cleanup_stale_temp_flag() {
  if [[ ! -f "$PERSIST_RECOVERY_FLAG" && ! -f "$BOOT_RECOVERY_FLAG" && -f "$TEMP_RECOVERY_FLAG" ]]; then
    rm -f "$TEMP_RECOVERY_FLAG" 2>/dev/null || true
  fi
}
HEARTBEAT_FILE="${HEARTBEAT_FILE:-/run/bascula/heartbeat}"
LEGACY_HEARTBEAT_FILE="${LEGACY_HEARTBEAT_FILE:-/run/bascula.alive}"
FAIL_COUNT_FILE="/opt/bascula/shared/userdata/app_fail_count"
SOFT_TIMEOUT="${SOFT_TIMEOUT:-45}"   # subir de 25s a 45s
MAX_HEARTBEAT_AGE="${MAX_HEARTBEAT_AGE:-12}"
MAX_SOFT_RETRIES="${MAX_SOFT_RETRIES:-2}"
SOFT_RETRY_DELAY="${SOFT_RETRY_DELAY:-3}"

log() {
  printf '[safe_run] %s\n' "$*" >&2
}

to_positive_int() {
  local value="$1"
  local fallback="$2"
  if [[ "$value" =~ ^[0-9]+$ ]]; then
    echo "$value"
  else
    echo "$fallback"
  fi
}

SOFT_TIMEOUT="$(to_positive_int "$SOFT_TIMEOUT" 45)"
MAX_HEARTBEAT_AGE="$(to_positive_int "$MAX_HEARTBEAT_AGE" 12)"
MAX_SOFT_RETRIES="$(to_positive_int "$MAX_SOFT_RETRIES" 2)"
SOFT_RETRY_DELAY="$(to_positive_int "$SOFT_RETRY_DELAY" 3)"

export PYTHONUNBUFFERED=1
cd "$APP_DIR"
export PYTHONPATH="$APP_DIR:${PYTHONPATH:-}"

if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3)"
fi

smoke_test() { [[ -r "$APP_DIR/main.py" ]]; }

should_force_recovery() {
  [[ -f "$PERSIST_RECOVERY_FLAG" ]] || [[ -f "$BOOT_RECOVERY_FLAG" ]] || [[ -f "$TEMP_RECOVERY_FLAG" ]]
}

start_recovery_target() {
  if ! command -v systemctl >/dev/null 2>&1; then
    log "systemctl no disponible; no se puede iniciar bascula-recovery.target"
    return 1
  fi

  if command -v sudo >/dev/null 2>&1; then
    sudo -n systemctl start bascula-recovery.target
  else
    systemctl start bascula-recovery.target
  fi
}

trigger_recovery_exit() {
  if [[ ! -f "$PERSIST_RECOVERY_FLAG" && ! -f "$BOOT_RECOVERY_FLAG" ]]; then
    touch "$TEMP_RECOVERY_FLAG" 2>/dev/null || true
  fi
  if should_force_recovery; then
    log "Forzando bascula-recovery.target"
    if ! start_recovery_target; then
      log "No se pudo iniciar recovery vía systemctl; saliendo con fallo para que systemd actúe"
      exit 3
    fi
    exit 0
  fi
  exit 2
}

if [[ -f "$BOOT_RECOVERY_FLAG" ]]; then
  log "Bandera de recovery detectada en boot"
  trigger_recovery_exit
fi

if should_force_recovery; then
  log "Flag de recovery detectada; no se relanza la UI"
  trigger_recovery_exit
fi

cleanup_stale_temp_flag

if ! smoke_test; then
  log "main.py no encontrado"
  exit 1
fi

heartbeat_paths=()
[[ -n "$HEARTBEAT_FILE" ]] && heartbeat_paths+=("$HEARTBEAT_FILE")
if [[ -n "$LEGACY_HEARTBEAT_FILE" && "$LEGACY_HEARTBEAT_FILE" != "$HEARTBEAT_FILE" ]]; then
  heartbeat_paths+=("$LEGACY_HEARTBEAT_FILE")
fi

heartbeat_fresh() {
  local now_ts="$1"
  local path
  local last
  for path in "${heartbeat_paths[@]}"; do
    [[ -n "$path" ]] || continue
    if [[ -f "$path" ]]; then
      last=$(stat -c %Y "$path" 2>/dev/null || echo 0)
      if (( last > 0 && now_ts - last <= MAX_HEARTBEAT_AGE )); then
        return 0
      fi
    fi
  done
  return 1
}

soft_retry_count=0

while :; do
  attempt=$((soft_retry_count + 1))
  log "Lanzando UI (intento ${attempt})"
  "$PY" "$APP_DIR/main.py" &
  app_pid=$!
  start_ts=$(date +%s)
  health_ok=0
  health_failed=0

  trap '[[ -n "${app_pid:-}" ]] && kill "$app_pid" 2>/dev/null || true' TERM INT

  while kill -0 "$app_pid" >/dev/null 2>&1; do
    now=$(date +%s)
    if heartbeat_fresh "$now"; then
      health_ok=1
      if [[ -f "$FAIL_COUNT_FILE" ]]; then
        rm -f "$FAIL_COUNT_FILE" 2>/dev/null || true
      fi
      break
    fi

    if (( now - start_ts >= SOFT_TIMEOUT )); then
      log "Heartbeat ausente tras ${SOFT_TIMEOUT}s; reiniciando UI"
      health_failed=1
      kill "$app_pid" 2>/dev/null || true
      break
    fi
    sleep 1
  done

  set +e
  wait "$app_pid"
  status=$?
  set -e
  trap - TERM INT
  unset app_pid

  if (( health_failed )); then
    if (( soft_retry_count < MAX_SOFT_RETRIES )); then
      soft_retry_count=$((soft_retry_count + 1))
      log "Reintento suave ${soft_retry_count}/${MAX_SOFT_RETRIES} tras fallo de heartbeat"
      sleep "$SOFT_RETRY_DELAY"
      continue
    fi
    log "Healthcheck fallido repetidamente; activando recovery"
    trigger_recovery_exit
  fi

  if (( status != 0 )); then
    log "Proceso UI terminó con status=${status}"
    exit "$status"
  fi

  if (( ! health_ok )); then
    log "Aplicación finalizó antes de señal de vida (no heartbeat observado)"
    exit 2
  fi

  if (( ${#heartbeat_paths[@]} )); then
    now=$(date +%s)
    if ! heartbeat_fresh "$now"; then
      log "Heartbeat obsoleto tras finalizar (>${MAX_HEARTBEAT_AGE}s)"
      exit 3
    fi
  fi

  break

done

post_cycle_cleanup() {
  cleanup_stale_temp_flag
}

post_cycle_cleanup

exit 0
SH

sudo chown pi:pi /opt/bascula/current/scripts/safe_run.sh
sudo chmod +x /opt/bascula/current/scripts/safe_run.sh

#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

maybe_run_ci_helper() {
  local action="${1:-}"
  if [[ "${action}" != "trigger" && "${action}" != "check" ]]; then
    return 1
  fi

  local dest_prefix=""
  if [[ "${BASCULA_CI:-0}" == "1" ]]; then
    dest_prefix="${DESTDIR:-/tmp/ci-root}"
  fi

  local persist_flag="${dest_prefix%/}/opt/bascula/shared/userdata/force_recovery"
  local boot_flag="${dest_prefix%/}/boot/bascula-recovery"
  local temp_flag="/tmp/bascula_force_recovery"
  local systemctl_bin="${SYSTEMCTL:-systemctl}"

  if [[ "${action}" == "check" ]]; then
    if [[ ! -f "${persist_flag}" && ! -f "${boot_flag}" && -f "${temp_flag}" ]]; then
      rm -f "${temp_flag}" 2>/dev/null || true
    fi
    return 0
  fi

  local reason="${2:-watchdog}"
  if [[ -f "${persist_flag}" || -f "${boot_flag}" ]]; then
    rm -f "${temp_flag}" 2>/dev/null || true
  elif [[ "${reason}" == "watchdog" ]]; then
    : >"${temp_flag}" 2>/dev/null || true
  else
    rm -f "${temp_flag}" 2>/dev/null || true
  fi

  if [[ -f "${persist_flag}" || -f "${boot_flag}" || -f "${temp_flag}" ]]; then
    if ! "${systemctl_bin}" start bascula-recovery.target; then
      return 3
    fi
    if [[ "${reason}" != "watchdog" ]]; then
      rm -f "${temp_flag}" 2>/dev/null || true
    fi
    return 0
  fi

  return 2
}

if maybe_run_ci_helper "${1:-}" "${2:-}"; then
  exit 0
else
  result=$?
  if [[ $result -ne 1 ]]; then
    exit "$result"
  fi
fi

APP_DIR="${APP_DIR:-/opt/bascula/current}"
PY="$APP_DIR/.venv/bin/python3"

PERSISTENT_RECOVERY_FLAG="${PERSISTENT_RECOVERY_FLAG:-/opt/bascula/shared/userdata/force_recovery}"
TEMP_RECOVERY_FLAG="${TEMP_RECOVERY_FLAG:-/tmp/bascula_force_recovery}"
BOOT_RECOVERY_FLAG="${BOOT_RECOVERY_FLAG:-/boot/bascula-recovery}"

HEARTBEAT_FILE="${HEARTBEAT_FILE:-/run/bascula/heartbeat}"
LEGACY_HEARTBEAT_FILE="${LEGACY_HEARTBEAT_FILE:-/run/bascula.alive}"
FAIL_COUNT_FILE="/opt/bascula/shared/userdata/app_fail_count"
SOFT_TIMEOUT="${SOFT_TIMEOUT:-45}"
MAX_HEARTBEAT_AGE="${MAX_HEARTBEAT_AGE:-12}"
MAX_SOFT_RETRIES="${MAX_SOFT_RETRIES:-2}"
SOFT_RETRY_DELAY="${SOFT_RETRY_DELAY:-3}"

log_journal() {
  if command -v logger >/dev/null 2>&1; then
    logger -t bascula-safe_run -- "$@"
  fi
}

log() {
  local msg
  msg="[safe_run] $*"
  printf '%s\n' "$msg" >&2
  log_journal "$msg"
}

cleanup_stale_temp_flag() {
  if [[ ! -f "$PERSISTENT_RECOVERY_FLAG" && ! -f "$BOOT_RECOVERY_FLAG" && -f "$TEMP_RECOVERY_FLAG" ]]; then
    log "Limpiando flag temporal obsoleta ${TEMP_RECOVERY_FLAG}"
    rm -f "$TEMP_RECOVERY_FLAG" 2>/dev/null || true
  fi
}

exit_with_code() {
  local code="$1"
  log "Finalizando safe_run con código ${code}"
  exit "$code"
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

smoke_test() {
  [[ -r "$APP_DIR/main.py" ]]
}

should_force_recovery() {
  [[ -f "$PERSISTENT_RECOVERY_FLAG" || -f "$BOOT_RECOVERY_FLAG" || -f "$TEMP_RECOVERY_FLAG" ]]
}

start_recovery_target() {
  local systemctl_bin
  systemctl_bin="${SYSTEMCTL:-systemctl}"

  if [[ "${BASCULA_CI:-0}" == "1" ]]; then
    if "${systemctl_bin}" start bascula-recovery.target; then
      return 0
    fi
    return 1
  fi

  if ! command -v "${systemctl_bin}" >/dev/null 2>&1; then
    return 1
  fi

  if command -v sudo >/dev/null 2>&1; then
    if sudo -n "${systemctl_bin}" start bascula-recovery.target; then
      return 0
    fi
  fi

  if "${systemctl_bin}" start bascula-recovery.target; then
    return 0
  fi
  return 1
}

trigger_recovery_exit() {
  local reason="${1:-watchdog}"

  case "$reason" in
    watchdog)
      : >"$TEMP_RECOVERY_FLAG" 2>/dev/null || true
      ;;
    external)
      rm -f "$TEMP_RECOVERY_FLAG" 2>/dev/null || true
      ;;
  esac

  if should_force_recovery; then
    log "Forzando bascula-recovery.target (reason=$reason)"
    if ! start_recovery_target; then
      log "No se pudo iniciar recovery vía systemctl; saliendo con 3"
      exit_with_code 3
    fi

    if [[ "$reason" != "watchdog" ]]; then
      rm -f "$TEMP_RECOVERY_FLAG" 2>/dev/null || true
    fi

    exit_with_code 0
  fi

  exit_with_code 2
}

log "Iniciando safe_run (pid $$)"
cleanup_stale_temp_flag

if [[ -f "$PERSISTENT_RECOVERY_FLAG" ]] || [[ -f "$BOOT_RECOVERY_FLAG" ]]; then
  log "Flag de recovery persistente/boot detectada; no se relanza la UI"
  trigger_recovery_exit "external"
fi

if should_force_recovery; then
  log "Flag temporal de recovery detectada; no se relanza la UI"
  trigger_recovery_exit
fi

if ! smoke_test; then
  log "main.py no encontrado"
  exit_with_code 1
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
    trigger_recovery_exit "watchdog"
  fi

  if (( status != 0 )); then
    log "Proceso UI terminó con status=${status}"
    exit_with_code "$status"
  fi

  if (( ! health_ok )); then
    log "Aplicación finalizó antes de señal de vida (no heartbeat observado)"
    exit_with_code 2
  fi

  if (( ${#heartbeat_paths[@]} )); then
    now=$(date +%s)
    if ! heartbeat_fresh "$now"; then
      log "Heartbeat obsoleto tras finalizar (> ${MAX_HEARTBEAT_AGE}s)"
      exit_with_code 3
    fi
  fi

  break

done

cleanup_stale_temp_flag
exit_with_code 0

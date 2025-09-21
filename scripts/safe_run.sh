sudo install -d -m 755 /opt/bascula/current/scripts

sudo tee /opt/bascula/current/scripts/safe_run.sh >/dev/null <<'SH'
#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/bascula/current}"
PY="$APP_DIR/.venv/bin/python3"
RECOVERY_FLAG="/opt/bascula/shared/userdata/force_recovery"
BOOT_FLAG="/boot/bascula-recovery"
ALIVE="/run/bascula.alive"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-25}"
MAX_HEARTBEAT_AGE="${MAX_HEARTBEAT_AGE:-12}"

log() {
  printf '[safe_run] %s\n' "$*" >&2
}

export PYTHONUNBUFFERED=1
cd "$APP_DIR"
export PYTHONPATH="$APP_DIR:${PYTHONPATH:-}"

if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3)"
fi

smoke_test() { [[ -r "$APP_DIR/main.py" ]]; }

if [[ -f "$RECOVERY_FLAG" || -f "$BOOT_FLAG" ]]; then
  log "Bandera de recovery detectada"
  exit 1
fi

if ! smoke_test; then
  log "main.py no encontrado"
  exit 1
fi

"$PY" "$APP_DIR/main.py" &
app_pid=$!
start_ts=$(date +%s)
health_ok=0
health_failed=0

trap '[[ -n "${app_pid:-}" ]] && kill "$app_pid" 2>/dev/null || true' TERM INT

while kill -0 "$app_pid" >/dev/null 2>&1; do
  now=$(date +%s)
  if [[ -f "$ALIVE" ]]; then
    last=$(stat -c %Y "$ALIVE" 2>/dev/null || echo 0)
    if (( last > 0 && now - last <= MAX_HEARTBEAT_AGE )); then
      health_ok=1
      break
    fi
  fi

  if (( now - start_ts >= HEALTH_TIMEOUT )); then
    log "Heartbeat ausente tras ${HEALTH_TIMEOUT}s; forzando recovery"
    mkdir -p "$(dirname "$RECOVERY_FLAG")"
    touch "$RECOVERY_FLAG"
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

if (( health_failed )); then
  exit 1
fi

if (( status != 0 )); then
  exit "$status"
fi

if (( ! health_ok )); then
  log "Aplicación finalizó antes de señal de vida"
fi

exit 0
SH

sudo chown pi:pi /opt/bascula/current/scripts/safe_run.sh
sudo chmod +x /opt/bascula/current/scripts/safe_run.sh

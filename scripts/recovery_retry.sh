#!/usr/bin/env bash
set -euo pipefail

FORCE_FLAG="/opt/bascula/shared/userdata/force_recovery"
BOOT_FLAG="/boot/bascula-recovery"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8080/health}"
WAIT_SECONDS=${WAIT_SECONDS:-30}

log() { printf '[recovery-retry] %s\n' "$*"; }

if [[ -f "$FORCE_FLAG" ]]; then
  log "Eliminando bandera force_recovery"
  rm -f "$FORCE_FLAG"
fi

if [[ -f "$BOOT_FLAG" ]]; then
  log "Eliminando bandera en /boot"
  if ! rm -f "$BOOT_FLAG" 2>/dev/null; then
    sudo rm -f "$BOOT_FLAG"
  fi
fi

systemctl reset-failed bascula-app.service bascula-recovery.service || true

log "Arrancando servicio bascula-app"
systemctl start bascula-app.service

for _ in $(seq 1 "$WAIT_SECONDS"); do
  if systemctl is-active --quiet bascula-app.service; then
    break
  fi
  sleep 1
done

check_health() {
  if command -v curl >/dev/null 2>&1; then
    curl -fsS --max-time 5 "$HEALTH_URL" >/dev/null 2>&1
  else
    python3 - "$HEALTH_URL" >/dev/null 2>&1 <<'PY'
import sys, urllib.request
url = sys.argv[1]
try:
    with urllib.request.urlopen(url, timeout=5) as resp:
        resp.read(1)
except Exception:
    sys.exit(1)
PY
  fi
}

for _ in $(seq 1 "$WAIT_SECONDS"); do
  if check_health; then
    log "Health endpoint OK"
    echo "Aplicación operativa"
    exit 0
  fi
  sleep 1
  if ! systemctl is-active --quiet bascula-app.service; then
    log "Servicio bascula-app se detuvo prematuramente"
    break
  fi
done

journalctl -u bascula-app.service -n 40 --no-pager || true
log "Health endpoint no respondió en ${WAIT_SECONDS}s"
exit 1

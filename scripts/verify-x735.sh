#!/usr/bin/env bash
set -euo pipefail

STATUS=0

log() { printf '[x735] %s\n' "$*"; }
warn() { printf '[x735][WARN] %s\n' "$*"; }

if command -v systemctl >/dev/null 2>&1; then
  systemctl --no-pager status x735-fan.service || warn 'x735-fan.service no activo'
else
  warn 'systemctl no disponible; estado del servicio omitido'
fi

UNIT_FILE="/etc/systemd/system/x735-fan.service"
if [[ -f "$UNIT_FILE" ]]; then
  log 'x735-fan.service presente en /etc/systemd/system'
else
  warn 'x735-fan.service ausente en /etc/systemd/system'
fi

SCRIPT="/usr/local/bin/x735.sh"
if [[ -x "$SCRIPT" ]]; then
  log '/usr/local/bin/x735.sh presente'
else
  warn '/usr/local/bin/x735.sh no encontrado o sin permisos'
fi

exit "$STATUS"

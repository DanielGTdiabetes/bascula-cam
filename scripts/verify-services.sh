#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATUS=0

log() { printf '[services] %s\n' "$*"; }
warn() { printf '[services][WARN] %s\n' "$*"; }
err() { printf '[services][ERR] %s\n' "$*" >&2; STATUS=1; }

SERVICE_DIR="$ROOT/etc/systemd/system"
EXPECTED_UNITS=(
  "bascula-ui.service"
  "bascula-recovery.service"
  "bascula-miniweb.service"
  "x735-fan.service"
)

for unit in "${EXPECTED_UNITS[@]}"; do
  if [[ -f "$SERVICE_DIR/$unit" ]]; then
    log "$unit presente en etc/systemd/system"
  else
    warn "$unit no encontrado en etc/systemd/system"
  fi
done

if command -v systemctl >/dev/null 2>&1; then
  for unit in "bascula-ui.service" "bascula-recovery.service" "bascula-miniweb.service"; do
    if systemctl list-units "$unit" >/dev/null 2>&1; then
      systemctl --no-pager status "$unit" || warn "$unit no activo"
    else
      warn "$unit no registrado en systemd"
    fi
  done
else
  warn 'systemctl no disponible; comprobaciones en vivo omitidas'
fi

if command -v loginctl >/dev/null 2>&1; then
  env_dump="$(loginctl show-environment 2>/dev/null || true)"
  if ! grep -q '^DISPLAY=' <<<"$env_dump"; then
    warn 'DISPLAY no exportado en sesión systemd (loginctl)'
  else
    log 'DISPLAY detectado en loginctl'
  fi
  if ! grep -q '^XAUTHORITY=' <<<"$env_dump"; then
    warn 'XAUTHORITY no definido en sesión systemd (loginctl)'
  else
    log 'XAUTHORITY detectado en loginctl'
  fi
else
  if [[ -z "${DISPLAY:-}" ]]; then
    warn 'DISPLAY no definido en entorno actual'
  else
    log "DISPLAY=${DISPLAY}"
  fi
  if [[ -z "${XAUTHORITY:-}" ]]; then
    warn 'XAUTHORITY no definido en entorno actual'
  else
    log "XAUTHORITY=${XAUTHORITY}"
  fi
fi

XINIT="$HOME/.xinitrc"
if [[ -f "$XINIT" ]]; then
  if grep -q 'safe_run.sh' "$XINIT"; then
    log '~/.xinitrc invoca safe_run.sh'
  else
    warn '~/.xinitrc no referencia safe_run.sh'
  fi
else
  warn '~/.xinitrc ausente'
fi

exit "$STATUS"

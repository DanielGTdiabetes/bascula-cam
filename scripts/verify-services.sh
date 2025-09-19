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

UI_UNIT="$SERVICE_DIR/bascula-ui.service"
if [[ -f "$UI_UNIT" ]]; then
  if grep -q 'Environment=DISPLAY=:0' "$UI_UNIT"; then
    log 'bascula-ui.service exporta DISPLAY=:0'
  else
    warn 'bascula-ui.service no fija DISPLAY=:0'
  fi
  if grep -q 'Environment=XAUTHORITY=' "$UI_UNIT"; then
    log 'bascula-ui.service define XAUTHORITY'
  else
    warn 'bascula-ui.service no define XAUTHORITY'
  fi
  if grep -q '^After=graphical.target' "$UI_UNIT"; then
    log 'bascula-ui.service espera a graphical.target'
  else
    warn 'bascula-ui.service no especifica After=graphical.target'
  fi
  if grep -q '^Restart=on-failure' "$UI_UNIT"; then
    log 'bascula-ui.service reinicia on-failure'
  else
    warn 'bascula-ui.service no define Restart=on-failure'
  fi
fi

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
  if grep -q '^DISPLAY=:0$' <<<"$env_dump"; then
    log 'DISPLAY=:0 presente en loginctl'
  else
    warn 'DISPLAY=:0 no presente en loginctl show-environment'
  fi
  if grep -q '^XAUTHORITY=' <<<"$env_dump"; then
    log 'XAUTHORITY detectado en loginctl'
  else
    warn 'XAUTHORITY no definido en sesión systemd (loginctl)'
  fi
else
  if [[ "${DISPLAY:-}" == ":0" ]]; then
    log 'DISPLAY=:0 disponible en el entorno actual'
  else
    warn 'DISPLAY=:0 no disponible en el entorno actual'
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

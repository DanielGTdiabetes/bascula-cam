#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_USER="${TARGET_USER:-${USER:-$(id -un)}}"
STATUS=0

log() { printf '[verify-scale] %s\n' "$1"; }
warn() { printf '[verify-scale][WARN] %s\n' "$1" >&2; }
err() { printf '[verify-scale][ERR] %s\n' "$1" >&2; STATUS=1; }

if [[ -n "${BASCULA_DEVICE:-}" ]]; then
  log "BASCULA_DEVICE=${BASCULA_DEVICE}"
else
  warn 'BASCULA_DEVICE no definido; se intentará autodetección'
fi

if id -nG "$TARGET_USER" | grep -Eq '\b(dialout|tty)\b'; then
  log "$TARGET_USER pertenece a dialout/tty"
else
  warn "$TARGET_USER no forma parte de los grupos dialout/tty"
fi

shopt -s nullglob
SERIAL_DEVICES=(/dev/ttyACM* /dev/ttyUSB*)
if (( ${#SERIAL_DEVICES[@]} == 0 )); then
  warn 'No se detectaron puertos serie /dev/ttyACM* ni /dev/ttyUSB*'
else
  log "Puertos serie detectados: ${SERIAL_DEVICES[*]}"
fi
shopt -u nullglob

RULE="$ROOT_DIR/etc/udev/rules.d/90-bascula.rules"
if [[ -f "$RULE" ]]; then
  log 'Regla udev 90-bascula.rules presente'
else
  warn 'Regla udev 90-bascula.rules ausente'
fi

if command -v python3 >/dev/null 2>&1; then
  if python3 "$ROOT_DIR/tools/check_scale.py"; then
    log 'tools/check_scale.py se ejecutó correctamente'
  else
    warn 'tools/check_scale.py devolvió error (hardware ausente?)'
  fi
else
  err 'python3 no disponible en PATH'
fi

exit $STATUS

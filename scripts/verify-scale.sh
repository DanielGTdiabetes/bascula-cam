#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_USER="${TARGET_USER:-$USER}"
STATUS=0

note() { printf '[verify-scale] %s\n' "$1"; }
warn() { printf '[verify-scale][WARN] %s\n' "$1" >&2; }
fail() { printf '[verify-scale][FAIL] %s\n' "$1" >&2; STATUS=1; }

device_hint="${BASCULA_DEVICE:-}";
if [[ -n "$device_hint" ]]; then
  note "BASCULA_DEVICE=$device_hint"
else
  warn 'BASCULA_DEVICE no establecido'
fi

USER_GROUPS=$(id -nG "$TARGET_USER")
if [[ "$USER_GROUPS" == *dialout* || "$USER_GROUPS" == *tty* ]]; then
  note "$TARGET_USER pertenece a grupos serie ($USER_GROUPS)"
else
  warn "$TARGET_USER no está en dialout/tty"
fi

shopt -s nullglob
DEVICES=(/dev/ttyACM* /dev/ttyUSB*)
if (( ${#DEVICES[@]} == 0 )); then
  warn 'No se detectaron dispositivos /dev/ttyACM* ni /dev/ttyUSB*'
else
  note "Dispositivos detectados: ${DEVICES[*]}"
fi

RULE="$ROOT_DIR/etc/udev/rules.d/90-bascula.rules"
if [[ -f "$RULE" ]]; then
  note "Regla udev presente en $RULE"
else
  warn "Regla udev 90-bascula.rules ausente"
fi

if command -v python >/dev/null 2>&1; then
  if python "$ROOT_DIR/tools/check_scale.py" >/dev/null 2>&1; then
    note 'tools/check_scale.py ejecutado con éxito'
  else
    warn 'tools/check_scale.py devolvió error (verificar hardware)'
  fi
else
  warn 'Python no disponible en PATH'
fi

exit $STATUS

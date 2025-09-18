#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_USER="${TARGET_USER:-$USER}"
STATUS=0

note() { printf '[verify-kiosk] %s\n' "$1"; }
fail() { printf '[verify-kiosk][FAIL] %s\n' "$1" >&2; STATUS=1; }
warn() { printf '[verify-kiosk][WARN] %s\n' "$1" >&2; }

if [[ ! -S /tmp/.X11-unix/X0 ]]; then
  fail 'Socket X0 no encontrado (/tmp/.X11-unix/X0)'
else
  note 'Socket X0 disponible'
fi

if command -v systemctl >/dev/null 2>&1; then
  if systemctl is-active --quiet bascula-miniweb.service; then
    note 'bascula-miniweb.service activo'
  else
    warn 'bascula-miniweb.service inactivo'
  fi
  if systemctl is-active --quiet x735.service; then
    note 'x735.service activo'
  else
    warn 'x735.service inactivo'
  fi
else
  warn 'systemctl no disponible; omitiendo comprobación de servicios'
fi

VOICE_DIR="/home/$TARGET_USER/.local/share/piper"
if [[ -f "$VOICE_DIR/.default-voice" ]]; then
  note "Voz Piper configurada ($(cat "$VOICE_DIR/.default-voice" 2>/dev/null))"
else
  warn "No se encontró $VOICE_DIR/.default-voice"
fi

VENV="$ROOT_DIR/.venv"
if [[ -d "$VENV" ]]; then
  OWNER="$(stat -c %U "$VENV")"
  if [[ "$OWNER" == "$TARGET_USER" ]]; then
    note "El venv pertenece a $TARGET_USER"
  else
    warn "El venv pertenece a $OWNER (se esperaba $TARGET_USER)"
  fi
else
  warn "Entorno virtual no encontrado en $VENV"
fi

PIP_CACHE="/home/$TARGET_USER/.cache/pip"
if [[ -d "$PIP_CACHE" ]]; then
  note "Caché pip localizada"
else
  warn "Caché pip no encontrada para $TARGET_USER"
fi

ASSETS_DIR="$ROOT_DIR/bascula/ui/assets/mascota/_gen"
if [[ -d "$ASSETS_DIR" ]] && compgen -G "$ASSETS_DIR/*.png" > /dev/null; then
  note "Assets de mascota presentes en $ASSETS_DIR"
else
  warn "Assets generados de mascota ausentes (se usará Canvas de emergencia)"
fi

exit $STATUS

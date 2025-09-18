#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_USER="${TARGET_USER:-${USER:-$(id -un)}}"
STATUS=0

log() { printf '[verify-kiosk] %s\n' "$1"; }
warn() { printf '[verify-kiosk][WARN] %s\n' "$1" >&2; }
err() { printf '[verify-kiosk][ERR] %s\n' "$1" >&2; STATUS=1; }

if [[ -S /tmp/.X11-unix/X0 ]]; then
  log 'Socket X0 disponible'
else
  warn 'No se encontró /tmp/.X11-unix/X0 (startx no iniciado?)'
fi

VENV="$ROOT_DIR/.venv"
if [[ -d "$VENV" ]]; then
  OWNER="$(stat -c %U "$VENV" 2>/dev/null || echo '?')"
  if [[ "$OWNER" == "$TARGET_USER" ]]; then
    log "Entorno virtual localizado en $VENV"
  else
    warn "El entorno virtual pertenece a $OWNER (esperado $TARGET_USER)"
  fi
else
  err "Falta entorno virtual en $VENV"
fi

ASSETS_DIR="$ROOT_DIR/bascula/ui/assets/mascota/_gen"
if compgen -G "$ASSETS_DIR"/*.png >/dev/null 2>&1; then
  log "Assets de mascota generados presentes"
else
  warn "Assets de mascota generados ausentes; se usará Canvas de emergencia"
fi

if [[ -d "$ROOT_DIR/.venv" ]]; then
  if [[ ! -r "$ROOT_DIR/.venv/bin/activate" ]]; then
    warn "El venv existe pero falta bin/activate legible"
  fi
fi

exit $STATUS

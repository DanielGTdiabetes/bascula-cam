#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_USER="${TARGET_USER:-${USER:-$(id -un)}}"
STATUS=0

log() { printf '[verify-kiosk] %s\n' "$*"; }
warn() { printf '[verify-kiosk][WARN] %s\n' "$*"; }
err() { printf '[verify-kiosk][ERR] %s\n' "$*" >&2; STATUS=1; }

if [[ -S /tmp/.X11-unix/X0 ]]; then
  log 'Socket X0 disponible'
else
  warn 'No se encontró /tmp/.X11-unix/X0 (modo headless?)'
fi

VENV="$ROOT_DIR/.venv"
if [[ -d "$VENV" ]]; then
  OWNER="$(stat -c %U "$VENV" 2>/dev/null || echo '?')"
  if [[ "$OWNER" == "$TARGET_USER" ]]; then
    log "Entorno virtual localizado en $VENV"
  else
    warn "El entorno virtual pertenece a $OWNER (esperado $TARGET_USER)"
  fi
  if [[ ! -r "$VENV/bin/activate" ]]; then
    warn 'bin/activate no es legible'
  fi
else
  warn "Falta entorno virtual en $VENV"
fi

SAFE_RUN="$ROOT_DIR/scripts/safe_run.sh"
if [[ -x "$SAFE_RUN" ]]; then
  log 'safe_run.sh es ejecutable'
else
  warn 'safe_run.sh no es ejecutable'
fi

ASSETS_DIR="$ROOT_DIR/bascula/ui/assets/mascota/_gen"
if compgen -G "$ASSETS_DIR"/*.png >/dev/null 2>&1; then
  log 'Assets de mascota generados presentes'
else
  warn 'Assets de mascota generados ausentes; se usará placeholder'
fi

RUNNER="$ROOT_DIR/scripts/run-ui.sh"
if [[ -x "$RUNNER" ]]; then
  log 'run-ui.sh es ejecutable'
else
  warn 'run-ui.sh no es ejecutable'
fi

exit "$STATUS"

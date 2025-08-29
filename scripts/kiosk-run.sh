#!/usr/bin/env bash
# Lanza la app dentro de X, aplicando ajustes de pantalla para kiosk.

set -euo pipefail

REPO_DIR="/home/pi/bascula-cam"
APP_MAIN="$REPO_DIR/main.py"
LOG_FILE="/home/pi/app.log"

# Export para imports relativos del repo
export PYTHONPATH="$REPO_DIR"

# Ajustes de pantalla "kiosk"
xset -dpms          # desactiva ahorro de energía
xset s off          # sin screensaver
xset s noblank      # no en negro
# (Si quieres brillo fijo con vcgencmd, lo añadimos luego)

# Cursor oculto (Xorg ya arranca con -nocursor, doble seguro)
unclutter -idle 0 -root >/dev/null 2>&1 || true

# Ejecuta la app y vuelca log
exec python3 "$APP_MAIN" >> "$LOG_FILE" 2>&1

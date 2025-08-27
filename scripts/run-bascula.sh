#!/usr/bin/env bash
set -euo pipefail

# --- Configurable paths ---
APP_DIR="${APP_DIR:-$HOME/bascula-cam}"
VENV_DIR="${VENV_DIR:-$APP_DIR/venv}"
PY="${PYTHON_BIN:-$VENV_DIR/bin/python3}"
MAIN="${MAIN_FILE:-$APP_DIR/main.py}"

# If venv doesn't exist, fall back to system python
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3)"
fi

# Force GUI display for Tkinter
export DISPLAY="${DISPLAY:-:0}"
# Optional: if your X session needs XAUTHORITY, uncomment next line and adjust user
# export XAUTHORITY="${XAUTHORITY:-/home/pi/.Xauthority}"

# Optionally speed up Tk on RPi
export TK_SILENCE_DEPRECATION=1

cd "$APP_DIR"
exec "$PY" "$MAIN"

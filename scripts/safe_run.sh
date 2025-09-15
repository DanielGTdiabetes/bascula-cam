#!/usr/bin/env bash
set -euo pipefail

# --- Paths
APP_DIR="/opt/bascula/current"
[ -d "$APP_DIR" ] || APP_DIR="$HOME/bascula-cam-main"
cd "$APP_DIR"

LOG_DIR="/var/log/bascula"
mkdir -p "$LOG_DIR" || true
LOG="$LOG_DIR/app.log"

# --- Entorno Xorg
export DISPLAY=${DISPLAY:-:0}
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
export LC_ALL=C.UTF-8
export LANG=C.UTF-8

# --- Recovery flag
REC_FLAG="/var/lib/bascula-updater/force_recovery"
if [ -f "$REC_FLAG" ]; then
  echo "[safe_run] Recovery flag encontrado, lanzando Recovery UI" | tee -a "$LOG"
  if [ -x ".venv/bin/python" ]; then
    exec .venv/bin/python -m bascula.ui.recovery_ui 2>>"$LOG"
  else
    exec python3 -m bascula.ui.recovery_ui 2>>"$LOG"
  fi
fi

# --- Venv opcional
PY=".venv/bin/python"
if [ -x "$PY" ]; then
  echo "[safe_run] Usando venv local" | tee -a "$LOG"
else
  PY="python3"
fi

# --- Desactivar ahorro de energía de pantalla y cursor
which xset >/dev/null 2>&1 && { xset s off -dpms; xset s noblank; }
which unclutter >/dev/null 2>&1 && { unclutter -idle 0.1 -root & }

# --- Lanzar app
echo "[safe_run] Lanzando app..." | tee -a "$LOG"
exec "$PY" main.py >>"$LOG" 2>&1

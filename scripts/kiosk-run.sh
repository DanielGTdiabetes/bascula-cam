tee /home/pi/bascula-cam/scripts/kiosk-run.sh >/dev/null <<'EOF'
#!/usr/bin/env bash
# Cliente X lanzado por xinit. Debug detallado + lanzamiento de Tk

set -u
REPO_DIR="/home/pi/bascula-cam"
APP_MAIN="$REPO_DIR/main.py"
LOG_FILE="/home/pi/app.log"

export PYTHONPATH="$REPO_DIR"
export DISPLAY="${DISPLAY:-:0}"
[ -f "/home/pi/.Xauthority" ] && export XAUTHORITY="/home/pi/.Xauthority"

{
  echo "[kiosk-run] ==== INICIO ===="
  echo "[kiosk-run] DEBUG: whoami=$(whoami)  pwd=$(pwd)"
  echo "[kiosk-run] DEBUG: DISPLAY=$DISPLAY  XAUTHORITY=${XAUTHORITY:-<none>}  PYTHONPATH=$PYTHONPATH"
  echo "[kiosk-run] DEBUG: which python3 -> $(command -v python3)"
  echo "[kiosk-run] Esperando socket X en /tmp/.X11-unix/X0 ..."
} >> "$LOG_FILE"

ok=0
for i in $(seq 1 150); do
  if [ -S /tmp/.X11-unix/X0 ]; then ok=1; break; fi
  sleep 0.1
done

{
  ls -l /tmp/.X11-unix || true
  echo "[kiosk-run] DEBUG: probando Tk mínimamente…"
} >> "$LOG_FILE"

# Comprobación mínima de Tk bajo este DISPLAY
python3 - <<'PY' >> "$LOG_FILE" 2>&1
import os, sys
print("[kiosk-run] PY: DISPLAY =", os.environ.get("DISPLAY"))
try:
    import tkinter as tk
    r = tk.Tk()
    r.withdraw()
    print("[kiosk-run] PY: Tk OK")
except Exception as e:
    print("[kiosk-run] PY: Tk FAILED:", e)
    sys.exit(2)
PY

{
  echo "[kiosk-run] Ajustes kiosk (xset/unclutter)…"
} >> "$LOG_FILE"

xset -dpms      >/dev/null 2>&1 || true
xset s off      >/dev/null 2>&1 || true
xset s noblank  >/dev/null 2>&1 || true
unclutter -idle 0 -root >/dev/null 2>&1 || true

{
  echo "[kiosk-run] Lanzando $APP_MAIN"
} >> "$LOG_FILE"

exec /usr/bin/python3 "$APP_MAIN" >> "$LOG_FILE" 2>&1
EOF

chmod +x /home/pi/bascula-cam/scripts/kiosk-run.sh
sudo systemctl restart bascula-kiosk
sleep 2
tail -n 200 /home/pi/app.log

sudo tee /home/pi/bascula-cam/scripts/kiosk-run.sh >/dev/null <<'EOF'
#!/usr/bin/env bash
set -u
REPO_DIR="/home/pi/bascula-cam"
APP_MAIN="$REPO_DIR/main.py"
LOG_FILE="/home/pi/app.log"
export PYTHONPATH="$REPO_DIR"
export DISPLAY="${DISPLAY:-:0}"
[ -f "/home/pi/.Xauthority" ] && export XAUTHORITY="/home/pi/.Xauthority"
echo "[kiosk-run] Esperando socket X en /tmp/.X11-unix/X0 ..." >> "$LOG_FILE"
for i in $(seq 1 150); do [ -S /tmp/.X11-unix/X0 ] && break; sleep 0.1; done
sleep 0.3
xset -dpms >/dev/null 2>&1 || true
xset s off >/dev/null 2>&1 || true
xset s noblank >/dev/null 2>&1 || true
unclutter -idle 0 -root >/dev/null 2>&1 || true
echo "[kiosk-run] Lanzando $APP_MAIN" >> "$LOG_FILE"
exec /usr/bin/python3 "$APP_MAIN" >> "$LOG_FILE" 2>&1
EOF
sudo chmod +x /home/pi/bascula-cam/scripts/kiosk-run.sh

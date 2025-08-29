sudo tee /home/pi/bascula-cam/scripts/kiosk-run.sh >/dev/null <<'EOF'
#!/usr/bin/env bash
# Cliente X lanzado por xinit. Espera a que el socket X exista y lanza la app.

set -u  # no abortar por comandos como xset/unclutter que pueden fallar si faltan extensiones

REPO_DIR="/home/pi/bascula-cam"
APP_MAIN="$REPO_DIR/main.py"
LOG_FILE="/home/pi/app.log"

# Entorno para la app
export PYTHONPATH="$REPO_DIR"
export DISPLAY=":0"
# Si existe cookie, úsala
[ -f "/home/pi/.Xauthority" ] && export XAUTHORITY="/home/pi/.Xauthority"

# Esperar a que X cree el socket (:0)
echo "[kiosk-run] Esperando socket X en /tmp/.X11-unix/X0 ..." >> "$LOG_FILE"
for i in $(seq 1 100); do
  if [ -S /tmp/.X11-unix/X0 ]; then
    break
  fi
  sleep 0.1
done
# pequeña pausa extra para que quede listo
sleep 0.3

# Kiosk: sin ahorro de energía/blank (ignorar si extension no existe)
xset -dpms      >/dev/null 2>&1 || true
xset s off      >/dev/null 2>&1 || true
xset s noblank  >/dev/null 2>&1 || true

# Ocultar cursor si está disponible
unclutter -idle 0 -root >/dev/null 2>&1 || true

echo "[kiosk-run] Lanzando $APP_MAIN" >> "$LOG_FILE"
exec /usr/bin/python3 "$APP_MAIN" >> "$LOG_FILE" 2>&1
EOF

sudo chmod +x /home/pi/bascula-cam/scripts/kiosk-run.sh
sudo systemctl restart bascula-kiosk

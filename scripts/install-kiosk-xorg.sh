#!/usr/bin/env bash
set -euo pipefail
APP_DIR="/opt/bascula/current"
[ -d "$APP_DIR" ] || APP_DIR="$HOME/bascula-cam-main"

mkdir -p "$HOME/.config/lxsession/LXDE-pi"
cat > "$HOME/.config/lxsession/LXDE-pi/autostart" <<'EOF'
@/opt/bascula/current/scripts/safe_run.sh
EOF
[ -d "$APP_DIR" ] || sed -i "s|/opt/bascula/current|$APP_DIR|g" "$HOME/.config/lxsession/LXDE-pi/autostart"

mkdir -p "$HOME/.config/autostart"
cat > "$HOME/.config/autostart/bascula.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Bascula
Exec=/opt/bascula/current/scripts/safe_run.sh
X-GNOME-Autostart-enabled=true
EOF
[ -d "$APP_DIR" ] || sed -i "s|/opt/bascula/current|$APP_DIR|g" "$HOME/.config/autostart/bascula.desktop"

chmod +x "$APP_DIR/scripts/safe_run.sh" 2>/dev/null || true
sudo systemctl disable bascula 2>/dev/null || true
echo "[kiosk-xorg] Instalación completada."


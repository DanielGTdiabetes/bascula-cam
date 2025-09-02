#!/usr/bin/env bash
# ==============================================================================
# scripts/bootstrap_bascula.sh — Setup de Báscula Digital Pro (Pi Zero 2 W)
# Simplificado: Wi-Fi de casa, LightDM+Openbox, autostart de la UI
# Cursor invisible permanente con unclutter-xfixes; sin salvapantallas
# ==============================================================================

set -euo pipefail

log()  { printf "\n\033[1;32m[bootstrap]\033[0m %s\n" "$*"; }
warn() { printf "\n\033[1;33m[bootstrap-warning]\033[0m %s\n" "$*"; }
err()  { printf "\n\033[1;31m[bootstrap-error]\033[0m %s\n" "$*" 1>&2; }

require_root() {
  if [[ $EUID -ne 0 ]]; then
    err "Ejecuta como root:  sudo bash ${BASH_SOURCE[0]}"
    exit 1
  fi
}

append_once() {
  local line="$1" file="$2"
  grep -qxF "$line" "$file" 2>/dev/null || echo "$line" >> "$file"
}

require_root

BASCULA_USER="bascula"
BASCULA_HOME="/home/${BASCULA_USER}"
REPO_DIR="${BASCULA_HOME}/bascula-cam"

# --- Paquetes base ---
log "1) Instalando paquetes base…"
apt-get update -y
apt-get install -y \
  git ca-certificates \
  xserver-xorg lightdm lightdm-gtk-greeter openbox \
  network-manager policykit-1 \
  python3-venv python3-pip python3-tk \
  rpicam-apps python3-picamera2 \
  unclutter-xfixes x11-xserver-utils \
  curl nano raspi-config

# --- LightDM autologin ---
log "2) Configurando LightDM autologin en '${BASCULA_USER}'…"
mkdir -p /etc/lightdm/lightdm.conf.d
cat > /etc/lightdm/lightdm.conf.d/50-bascula-autologin.conf <<EOF
[Seat:*]
autologin-user=${BASCULA_USER}
autologin-user-timeout=0
autologin-session=openbox
greeter-session=lightdm-gtk-greeter
EOF

# --- Autostart de Openbox ---
log "3) Configurando autostart de Openbox…"
sudo -u ${BASCULA_USER} bash -lc '
mkdir -p ~/.config/openbox ~/.local/bin

# Script de lanzamiento de la app
cat > ~/.local/bin/start-bascula.sh << "SH"
#!/usr/bin/env bash
set -euo pipefail
echo "$(date) - start-bascula.sh lanzado" >> /home/'${BASCULA_USER}'/autostart.log 2>&1
cd /home/'${BASCULA_USER}'/bascula-cam
if [ ! -d .venv ]; then
  python3 -m venv --system-site-packages .venv >> /home/'${BASCULA_USER}'/autostart.log 2>&1
fi
source .venv/bin/activate
echo "$(date) - ejecutando main.py" >> /home/'${BASCULA_USER}'/autostart.log 2>&1
exec python3 /home/'${BASCULA_USER}'/bascula-cam/main.py >> /home/'${BASCULA_USER}'/autostart.log 2>&1
SH
chmod +x ~/.local/bin/start-bascula.sh

# Autostart de Openbox
cat > ~/.config/openbox/autostart << "EOF2"
#!/usr/bin/env bash
# ===== Autostart Openbox Báscula =====

# Cursor normal (por compatibilidad; no visible igual con unclutter-xfixes)
xsetroot -cursor_name left_ptr &

# Desactivar salvapantallas y apagado de pantalla
xset s off          # sin screensaver
xset -dpms          # sin gestión de energía
xset s noblank      # no poner en negro

# Cursor invisible permanente
unclutter-xfixes -grab &

# Lanzar la báscula
/home/'${BASCULA_USER}'/.local/bin/start-bascula.sh &
EOF2
chmod +x ~/.config/openbox/autostart
'

# --- HDMI 1024x600 y UART ---
log "4) Ajustando HDMI y UART…"
BOOT_FW_DIR="/boot/firmware"
[ -d "$BOOT_FW_DIR" ] || BOOT_FW_DIR="/boot"
CONFIG_TXT="${BOOT_FW_DIR}/config.txt"
CMDLINE_TXT="${BOOT_FW_DIR}/cmdline.txt"

append_once "dtoverlay=vc4-kms-v3d" "${CONFIG_TXT}"
append_once "hdmi_force_hotplug=1" "${CONFIG_TXT}"
append_once "hdmi_group=2" "${CONFIG_TXT}"
append_once "hdmi_mode=87" "${CONFIG_TXT}"
append_once "hdmi_cvt=1024 600 60 3 0 0 0" "${CONFIG_TXT}"
append_once "enable_uart=1" "${CONFIG_TXT}"
append_once "dtoverlay=disable-bt" "${CONFIG_TXT}"

sed -i 's/console=serial0,[0-9]* //g' "${CMDLINE_TXT}" || true

# --- Final ---
log "5) Reiniciando para aplicar cambios…"
systemctl set-default graphical.target
reboot

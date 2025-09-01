#!/usr/bin/env bash
set -euo pipefail

# =============================================
# Bascula Digital - Bootstrap de reinstalación
# Probado en Raspberry Pi OS (Bookworm) 64-bit
# Ejecutar como root:
#   sudo bash install_bascula.sh
#
# Puedes sobreescribir por env:
#   REPO_URL="https://github.com/USUARIO/bascula-cam.git"
#   APP_DIR="/home/pi/bascula-cam"
#   AP_SSID="BasculaAP" AP_CHANNEL="1" AP_PSK="bascula1234"
#   SERIAL_PORT="/dev/serial0" SERIAL_BAUD="115200"
# =============================================

# --------- CONFIG PREDETERMINADA ---------
REPO_URL="${REPO_URL:-https://github.com/DanielGTdiabetes/bascula-cam.git}"

PI_USER="${SUDO_USER:-${USER}}"
HOME_DIR="$(getent passwd "$PI_USER" | cut -d: -f6)"
APP_DIR="${APP_DIR:-${HOME_DIR}/bascula-cam}"
VENV_DIR="${APP_DIR}/.venv"
PY_ENTRY="${PY_ENTRY:-${APP_DIR}/main.py}"
PY_LOG="${PY_LOG:-${HOME_DIR}/app.log}"
PYTHONPATH_VAL="${APP_DIR}"

SERVICE_NAME="${SERVICE_NAME:-bascula.service}"
SERVICE_SRC="${SERVICE_SRC:-$(pwd)/systemd/${SERVICE_NAME}}"
SERVICE_DST="/etc/systemd/system/${SERVICE_NAME}"

NM_PROFILE_NAME="${NM_PROFILE_NAME:-bascula-ap.nmconnection}"
NM_SRC="${NM_SRC:-$(pwd)/networkmanager/${NM_PROFILE_NAME}}"
NM_DST="/etc/NetworkManager/system-connections/${NM_PROFILE_NAME}"

AP_SSID="${AP_SSID:-BasculaAP}"
AP_CHANNEL="${AP_CHANNEL:-1}"          # 1 u 11 suelen ser los más compatibles
AP_PSK="${AP_PSK:-bascula1234}"

SERIAL_PORT="${SERIAL_PORT:-/dev/serial0}"
SERIAL_BAUD="${SERIAL_BAUD:-115200}"

# --------- UTILIDADES ---------
log()  { echo -e "\e[1;32m[OK]\e[0m $*"; }
warn() { echo -e "\e[1;33m[WARN]\e[0m $*"; }
err()  { echo -e "\e[1;31m[ERR]\e[0m $*" >&2; }

need_root() {
  if [[ $EUID -ne 0 ]]; then
    err "Ejecuta como root:  sudo bash install_bascula.sh"
    exit 1
  fi
}

ensure_user() {
  if ! id -u "$PI_USER" >/dev/null 2>&1; then
    err "El usuario '${PI_USER}' no existe."
    exit 1
  fi
}

replace_var_in_file() {
  local file="$1" key="$2" value="$3"
  sed -i "s|__${key}__|${value}|g" "$file"
}

# --------- INICIO ---------
need_root
ensure_user

echo "==> Usuario detectado: ${PI_USER}"
echo "==> HOME: ${HOME_DIR}"
echo "==> APP_DIR: ${APP_DIR}"

# --------- Paquetes del sistema ---------
log "Actualizando e instalando paquetes necesarios…"
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  git curl ca-certificates \
  network-manager \
  python3 python3-venv python3-pip python3-tk python3-serial \
  python3-opencv python3-pil \
  python3-picamera2 libcamera-apps \
  libatlas-base-dev \
  xserver-xorg xinit x11-xserver-utils \
  fonts-dejavu unclutter jq

# --------- NetworkManager (config base) ---------
log "Configurando NetworkManager (keyfile/ifupdown, sin MAC aleatoria)…"
mkdir -p /etc/NetworkManager
cat >/etc/NetworkManager/NetworkManager.conf <<'EOF'
[main]
plugins=ifupdown,keyfile

[ifupdown]
managed=true

[device]
wifi.scan-rand-mac-address=no

[keyfile]
unmanaged-devices=none
EOF

# --------- Perfil AP WPA2-PSK ---------
log "Instalando perfil AP WPA2-PSK…"
mkdir -p /etc/NetworkManager/system-connections

if [[ -f "$NM_SRC" ]]; then
  install -m 600 -o root -g root "$NM_SRC" "$NM_DST"
else
  warn "No se encontró ${NM_SRC}, creando perfil AP por defecto…"
  cat >"$NM_DST" <<'EOF'
[connection]
id=bascula-ap
uuid=086433ef-c189-4f29-a99f-3e575ed23ccc
type=wifi
interface-name=wlan0
autoconnect=true
autoconnect-retries=0

[wifi]
band=bg
mode=ap
ssid=__AP_SSID__
channel=__AP_CHANNEL__
cloned-mac-address=preserve
mac-address-randomization=0

[wifi-security]
key-mgmt=wpa-psk
psk=__AP_PSK__
proto=rsn
group=ccmp
pmf=0

[ipv4]
method=shared

[ipv6]
addr-gen-mode=default
method=ignore
EOF
  chmod 600 "$NM_DST"; chown root:root "$NM_DST"
fi

# Parametrizar SSID/canal/PSK
replace_var_in_file "$NM_DST" "AP_SSID"   "$AP_SSID"
replace_var_in_file "$NM_DST" "AP_CHANNEL" "$AP_CHANNEL"
replace_var_in_file "$NM_DST" "AP_PSK"    "$AP_PSK"

# Drop-in para asegurar permisos correctos en cada arranque
log "Creando drop-in para asegurar permisos del perfil AP en cada boot…"
mkdir -p /etc/systemd/system/NetworkManager.service.d
cat >/etc/systemd/system/NetworkManager.service.d/override.conf <<EOF
[Service]
ExecStartPre=/bin/chown root:root ${NM_DST}
ExecStartPre=/bin/chmod 600 ${NM_DST}
ExecStartPre=/sbin/iw reg set ES
EOF

systemctl daemon-reload
systemctl restart NetworkManager || true
sleep 2

# --------- UART/GPIO: liberar serial y grupos ---------
log "Ajustando UART/GPIO (remover consola, getty; añadir grupos)…"
CMDLINE="/boot/cmdline.txt"
if grep -q "console=serial0" "$CMDLINE" || grep -q "console=ttyAMA0" "$CMDLINE"; then
  sed -i -E 's/\s*console=(serial0|ttyAMA0),[0-9]+\s*//g' "$CMDLINE"
  log "Consola serie eliminada de cmdline.txt"
fi

CONFIG="/boot/config.txt"
grep -q "^enable_uart=1"        "$CONFIG" || echo "enable_uart=1" >> "$CONFIG"
grep -q "^dtparam=i2c_arm=on"   "$CONFIG" || echo "dtparam=i2c_arm=on" >> "$CONFIG"
grep -q "^dtparam=spi=on"       "$CONFIG" || echo "dtparam=spi=on" >> "$CONFIG"
# Si quieres ttyAMA0 en los pines y NO usar Bluetooth, descomenta:
# if ! grep -q "^dtoverlay=disable-bt" "$CONFIG"; then
#   echo "dtoverlay=disable-bt" >> "$CONFIG"
#   systemctl disable --now hciuart.service || true
# fi

systemctl disable --now serial-getty@ttyAMA0.service || true
systemctl disable --now serial-getty@ttyS0.service   || true

usermod -aG dialout,tty,gpio,video "$PI_USER" || true

# --------- Clonado/actualización del repositorio ---------
if [[ -d "${APP_DIR}/.git" ]]; then
  log "Repo existente. Actualizando…"
  sudo -u "${PI_USER}" bash -lc "cd '${APP_DIR}' && git fetch --all && git reset --hard origin/main && git pull --ff-only"
else
  log "Clonando repositorio…"
  sudo -u "${PI_USER}" bash -lc "git clone --depth 1 '${REPO_URL}' '${APP_DIR}'"
fi

# --------- Virtualenv + dependencias ---------
log "Creando entorno virtual e instalando requirements (si existen)…"
sudo -u "${PI_USER}" bash -lc "python3 -m venv '${VENV_DIR}'"
sudo -u "${PI_USER}" bash -lc "source '${VENV_DIR}/bin/activate' && \
  pip install --upgrade pip && \
  if [[ -f '${APP_DIR}/requirements.txt' ]]; then pip install -r '${APP_DIR}/requirements.txt'; else echo 'No hay requirements.txt, continuando…'; fi"

# --------- Lanzador CLI /usr/local/bin/bascula ---------
log "Creando lanzador /usr/local/bin/bascula…"
cat >/usr/local/bin/bascula <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
PI_USER="${SUDO_USER:-${USER}}"
HOME_DIR="$(getent passwd "$PI_USER" | cut -d: -f6)"
APP_DIR="${APP_DIR:-${HOME_DIR}/bascula-cam}"
VENV_DIR="${APP_DIR}/.venv"
PY_ENTRY="${PY_ENTRY:-${APP_DIR}/main.py}"
PY_LOG="${PY_LOG:-${HOME_DIR}/app.log}"
export PYTHONPATH="${APP_DIR}"
cd "${APP_DIR}"
# Oculta el cursor si hay X en marcha
if command -v unclutter >/dev/null 2>&1; then
  pgrep -x unclutter >/dev/null || (unclutter -idle 0.1 -root >/dev/null 2>&1 &)
fi
source "${VENV_DIR}/bin/activate"
exec python3 "${PY_ENTRY}" >> "${PY_LOG}" 2>&1
EOF
chmod +x /usr/local/bin/bascula

# Alias en .bashrc
if ! sudo -u "${PI_USER}" grep -q 'alias bascula=' "${HOME_DIR}/.bashrc"; then
  echo "alias bascula='/usr/local/bin/bascula'" >> "${HOME_DIR}/.bashrc"
fi

# --------- Sesión X mínima /usr/local/bin/bascula-xsession ---------
log "Creando sesión X mínima /usr/local/bin/bascula-xsession…"
cat >/usr/local/bin/bascula-xsession <<'EOF'
#!/usr/bin/env bash
xset -dpms
xset s off
xset s noblank
if command -v unclutter >/dev/null 2>&1; then
  pgrep -x unclutter >/dev/null || (unclutter -idle 0.1 -root >/dev/null 2>&1 &)
fi
exec /usr/local/bin/bascula
EOF
chmod +x /usr/local/bin/bascula-xsession

# ~/.xinitrc
log "Escribiendo ~/.xinitrc…"
sudo -u "${PI_USER}" tee "${HOME_DIR}/.xinitrc" >/dev/null <<'EOF'
#!/bin/sh
xset -dpms
xset s off
xset s noblank
if command -v unclutter >/dev/null 2>&1; then
  pgrep -x unclutter >/dev/null || (unclutter -idle 0.1 -root >/dev/null 2>&1 &)
fi
exec /usr/local/bin/bascula
EOF
chown "${PI_USER}:${PI_USER}" "${HOME_DIR}/.xinitrc"
chmod +x "${HOME_DIR}/.xinitrc"

# --------- Servicio systemd (desde el repo si existe) ---------
log "Creando servicio systemd ${SERVICE_NAME}…"
if [[ -f "$SERVICE_SRC" ]]; then
  install -m 644 -o root -g root "$SERVICE_SRC" "$SERVICE_DST"
else
  warn "No existe ${SERVICE_SRC}, generando servicio por defecto…"
  cat >"$SERVICE_DST" <<EOF
[Unit]
Description=Bascula Digital (Xinit autostart)
After=network-online.target NetworkManager.service
Wants=network-online.target

[Service]
Type=simple
User=${PI_USER}
WorkingDirectory=${APP_DIR}
Environment=PYTHONPATH=${PYTHONPATH_VAL}
Environment=DISPLAY=:0
Environment=SERIAL_PORT=${SERIAL_PORT}
Environment=SERIAL_BAUD=${SERIAL_BAUD}
ExecStart=/usr/bin/startx /usr/local/bin/bascula-xsession -- -nocursor
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
fi

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"

# --------- Script de actualización rápida ---------
log "Creando /usr/local/bin/bascula-update…"
cat >/usr/local/bin/bascula-update <<EOF
#!/usr/bin/env bash
set -euo pipefail
PI_USER="${PI_USER}"
APP_DIR="${APP_DIR}"
VENV_DIR="${VENV_DIR}"
SERVICE_NAME="${SERVICE_NAME}"
sudo -u "\${PI_USER}" bash -lc "cd '\${APP_DIR}' && git fetch --all && git reset --hard origin/main && git pull --ff-only"
sudo -u "\${PI_USER}" bash -lc "source '\${VENV_DIR}/bin/activate' && if [[ -f '\${APP_DIR}/requirements.txt' ]]; then pip install -r '\${APP_DIR}/requirements.txt'; fi"
sudo systemctl restart "\${SERVICE_NAME}"
echo "Actualizado y reiniciado."
EOF
chmod +x /usr/local/bin/bascula-update

# --------- Log app ---------
touch "${PY_LOG}"
chown "${PI_USER}:${PI_USER}" "${PY_LOG}"

log "Instalación completada."
echo "Comandos útiles:"
echo "  • Iniciar ahora:     sudo systemctl start ${SERVICE_NAME}"
echo "  • Ver estado:        systemctl status ${SERVICE_NAME} -n 50"
echo "  • Logs en vivo:      journalctl -u ${SERVICE_NAME} -f"
echo "  • Ejecutar manual:   sudo -u ${PI_USER} startx"
echo "  • Alias rápido:      bascula"
echo "  • Actualizar código: sudo /usr/local/bin/bascula-update"
echo "  • (AP) SSID: ${AP_SSID} | Canal: ${AP_CHANNEL} | Clave: ${AP_PSK}"
echo "  • (UART) ${SERIAL_PORT} @ ${SERIAL_BAUD}"
echo "Reinicia para aplicar todo (UART/AP): sudo reboot"

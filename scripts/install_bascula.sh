#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Bascula Digital Pro — Instalador todo en uno (vía SSH)
# Probado en: Debian 12/Bookworm en Raspberry Pi Zero 2 W
# Hace:
#  - Repos Raspberry Pi + keyring (libcamera/rpicam-apps)
#  - Paquetes base: Xorg, Tk, Picamera2, rpicam-apps, etc.
#  - HDMI forzado 1024x600 (evita "no screens found")
#  - Permisos Xorg (Xwrapper) para lanzar desde systemd
#  - UART libre (sin consola), grupos y servicios serial
#  - NetworkManager + AP WPA2 (BasculaAP) + drop-in permisos
#  - venv con --system-site-packages y requirements.txt
#  - Lanzadores y servicio systemd de la app
# ============================================================

# ===== Variables (puedes sobreescribirlas al invocar) =====
PI_USER="${PI_USER:-pi}"
REPO_URL="${REPO_URL:-https://github.com/DanielGTdiabetes/bascula-cam.git}"
APP_DIR="${APP_DIR:-/home/${PI_USER}/bascula-cam}"
VENV_DIR="${VENV_DIR:-${APP_DIR}/.venv}"
PY_ENTRY="${PY_ENTRY:-${APP_DIR}/main.py}"
SERVICE_NAME="${SERVICE_NAME:-bascula.service}"

# Wi-Fi AP
AP_SSID="${AP_SSID:-BasculaAP}"
AP_PSK="${AP_PSK:-bascula1234}"
AP_CHANNEL="${AP_CHANNEL:-1}"   # 1 u 11 suelen ir mejor

# UART / Serie
SERIAL_PORT="${SERIAL_PORT:-/dev/serial0}"
SERIAL_BAUD="${SERIAL_BAUD:-115200}"

# HDMI (pantalla 7” típica 1024×600; ajusta si usas otra)
HDMI_W="${HDMI_W:-1024}"
HDMI_H="${HDMI_H:-600}"
HDMI_FPS="${HDMI_FPS:-60}"

# ============================================================
log(){ echo -e "\e[1;32m[OK]\e[0m $*"; }
warn(){ echo -e "\e[1;33m[WARN]\e[0m $*"; }
err(){ echo -e "\e[1;31m[ERR]\e[0m $*" >&2; }

need_root(){
  if [[ $EUID -ne 0 ]]; then
    err "Ejecuta como root: sudo bash $(basename "$0")"
    exit 1
  fi
}

detect_bootdir(){
  if [[ -d /boot/firmware ]]; then
    BOOTDIR="/boot/firmware"
  else
    BOOTDIR="/boot"
  fi
  log "BOOTDIR = ${BOOTDIR}"
}

ensure_user(){
  id -u "$PI_USER" >/dev/null 2>&1 || { err "Usuario ${PI_USER} no existe"; exit 1; }
  HOME_DIR="$(getent passwd "$PI_USER" | cut -d: -f6)"
}

replace_in_file(){ # file key value  (replace __KEY__ with value)
  sed -i "s|__${2}__|${3}|g" "$1"
}

# ============================================================
need_root
detect_bootdir
ensure_user

echo "==> Usuario: ${PI_USER}"
echo "==> APP_DIR: ${APP_DIR}"

# ---------- Repos & Keyrings (Raspberry Pi) ----------
log "Configurando repositorios Raspberry Pi + keyring…"
apt-get update -y
apt-get install -y ca-certificates curl gnupg

# Keyring oficial
apt-get install -y raspberrypi-archive-keyring

# Deja SOLO el repo de archive.raspberrypi.org con firma
tee /etc/apt/sources.list.d/raspi.list >/dev/null <<'EOF'
deb [signed-by=/usr/share/keyrings/raspberrypi-archive-keyring.gpg] http://archive.raspberrypi.org/debian/ bookworm main
EOF

# (Opcional) elimina cualquier repo raspbian viejo para evitar NO_PUBKEY
grep -R "raspbian.raspberrypi.org" /etc/apt/sources.list* -n || true
# Si aparece, puedes comentar/borrar líneas manualmente o:
# sed -i 's|^deb .*raspbian.raspberrypi.org.*|# &|g' /etc/apt/sources.list.d/raspi.list 2>/dev/null || true

apt-get update -y

# ---------- Paquetes base del sistema ----------
log "Instalando paquetes base…"
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  git curl coreutils sed grep procps util-linux jq \
  network-manager \
  python3 python3-venv python3-pip python3-tk python3-serial \
  python3-opencv python3-pil \
  python3-picamera2 libcamera-apps v4l-utils libcamera-apps \
  xserver-xorg xinit x11-xserver-utils \
  fonts-dejavu unclutter libatlas-base-dev

# ---------- Cámara: utilidades modernas ----------
log "Asegurando utilidades rpicam…"
apt-get purge -y rpicam-apps-lite || true
apt-get install -y rpicam-apps || true

# ---------- HDMI: forzar modo seguro para pantallas sin EDID ----------
log "Forzando HDMI ${HDMI_W}x${HDMI_H}@${HDMI_FPS} + KMS en ${BOOTDIR}/config.txt…"
CONF="${BOOTDIR}/config.txt"
# Evita duplicados:
sed -i '/^hdmi_force_hotplug=/d;/^hdmi_group=/d;/^hdmi_mode=/d;/^hdmi_cvt=/d;/^dtoverlay=vc4-/d' "$CONF"
cat >>"$CONF" <<EOF

# --- Bascula: HDMI forzado y KMS ---
hdmi_force_hotplug=1
hdmi_group=2
hdmi_mode=87
hdmi_cvt=${HDMI_W} ${HDMI_H} ${HDMI_FPS} 3 0 0 0
dtoverlay=vc4-kms-v3d
EOF

# ---------- Xorg: permitir ejecución desde systemd ----------
log "Configurando Xwrapper (permitir X desde servicio)…"
mkdir -p /etc/X11
tee /etc/X11/Xwrapper.config >/dev/null <<'EOF'
allowed_users=anybody
needs_root_rights=yes
EOF

# ---------- UART: liberar serial GPIO14/15 ----------
log "Liberando UART (sin consola) y habilitando buses…"
CMDLINE="${BOOTDIR}/cmdline.txt"
# Quita console=serial0/ttyAMA0
sed -i -E 's/\s*console=(serial0|ttyAMA0),[0-9]+\s*//g' "$CMDLINE" || true

# Config.txt: enable_uart=1 + (opcional) disable-bt para ttyAMA0
sed -i '/^enable_uart=/d;/^dtoverlay=disable-bt/d;/^dtparam=i2c_arm=/d;/^dtparam=spi=/d' "$CONF"
cat >>"$CONF" <<'EOF'
# --- Bascula: UART + I2C/SPI ---
enable_uart=1
# Descomenta si quieres liberar ttyAMA0 deshabilitando BT:
dtoverlay=disable-bt
dtparam=i2c_arm=on
dtparam=spi=on
EOF

# Desactiva getty en serial
systemctl disable --now serial-getty@ttyAMA0.service || true
systemctl disable --now serial-getty@ttyS0.service   || true

# Grupos del usuario
usermod -aG dialout,tty,gpio,video "${PI_USER}" || true

# ---------- NetworkManager: config + AP ----------
log "Configurando NetworkManager y AP WPA2…"
mkdir -p /etc/NetworkManager
tee /etc/NetworkManager/NetworkManager.conf >/dev/null <<'EOF'
[main]
plugins=ifupdown,keyfile

[ifupdown]
managed=true

[device]
wifi.scan-rand-mac-address=no

[keyfile]
unmanaged-devices=none
EOF

mkdir -p /etc/NetworkManager/system-connections
NM_DST="/etc/NetworkManager/system-connections/bascula-ap.nmconnection"
tee "$NM_DST" >/dev/null <<'EOF'
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
replace_in_file "$NM_DST" "AP_SSID"    "$AP_SSID"
replace_in_file "$NM_DST" "AP_CHANNEL" "$AP_CHANNEL"
replace_in_file "$NM_DST" "AP_PSK"     "$AP_PSK"
chown root:root "$NM_DST"; chmod 600 "$NM_DST"

# Drop-in para asegurar permisos correctos en cada boot
mkdir -p /etc/systemd/system/NetworkManager.service.d
tee /etc/systemd/system/NetworkManager.service.d/override.conf >/dev/null <<EOF
[Service]
ExecStartPre=/bin/chown root:root ${NM_DST}
ExecStartPre=/bin/chmod 600 ${NM_DST}
ExecStartPre=/sbin/iw reg set ES
EOF

systemctl daemon-reload
systemctl restart NetworkManager || true

# ---------- Código de la app ----------
log "Clonando/actualizando repositorio de la app…"
if [[ -d "${APP_DIR}/.git" ]]; then
  sudo -u "${PI_USER}" bash -lc "cd '${APP_DIR}' && git fetch --all && git reset --hard origin/main && git pull --ff-only"
else
  sudo -u "${PI_USER}" bash -lc "git clone --depth 1 '${REPO_URL}' '${APP_DIR}'"
fi

# ---------- venv con --system-site-packages ----------
log "Creando venv con acceso a paquetes APT (Picamera2)…"
sudo -u "${PI_USER}" bash -lc "python3 -m venv --system-site-packages '${VENV_DIR}'"
sudo -u "${PI_USER}" bash -lc "source '${VENV_DIR}/bin/activate' && pip install --upgrade pip && \
  if [[ -f '${APP_DIR}/requirements.txt' ]]; then pip install -r '${APP_DIR}/requirements.txt'; else echo 'No hay requirements.txt'; fi"

# ---------- Lanzadores ----------
log "Creando lanzadores…"
/usr/bin/env bash -c "cat > /usr/local/bin/bascula" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/home/pi/bascula-cam}"
VENV_DIR="${VENV_DIR:-${APP_DIR}/.venv}"
PY_ENTRY="${PY_ENTRY:-${APP_DIR}/main.py}"
PY_LOG="${PY_LOG:-/home/pi/app.log}"
export PYTHONPATH="/usr/lib/python3/dist-packages:${APP_DIR}:${PYTHONPATH:-}"
cd "${APP_DIR}"
if command -v unclutter >/dev/null 2>&1; then
  pgrep -x unclutter >/dev/null || (unclutter -idle 0.1 -root >/dev/null 2>&1 &)
fi
source "${VENV_DIR}/bin/activate"
exec python3 "${PY_ENTRY}" >> "${PY_LOG}" 2>&1
EOF
chmod +x /usr/local/bin/bascula

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

# ---------- Servicio systemd ----------
log "Creando servicio systemd ${SERVICE_NAME}…"
tee /etc/systemd/system/${SERVICE_NAME} >/dev/null <<EOF
[Unit]
Description=Bascula Digital (Xinit autostart)
After=network-online.target NetworkManager.service
Wants=network-online.target

[Service]
Type=simple
User=${PI_USER}
WorkingDirectory=${APP_DIR}
Environment=PYTHONPATH=/usr/lib/python3/dist-packages:${APP_DIR}
Environment=DISPLAY=:0
Environment=SERIAL_PORT=${SERIAL_PORT}
Environment=SERIAL_BAUD=${SERIAL_BAUD}
ExecStart=/usr/bin/xinit /usr/local/bin/bascula-xsession -- :0 vt1 -nocursor
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

touch "/home/${PI_USER}/app.log"; chown "${PI_USER}:${PI_USER}" "/home/${PI_USER}/app.log"

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"

# ---------- Mensajes finales ----------
log "Instalación completada."
echo
echo "AP Wi-Fi  : SSID=${AP_SSID}  | Clave=${AP_PSK}  | Canal=${AP_CHANNEL}"
echo "UART      : ${SERIAL_PORT} @ ${SERIAL_BAUD}"
echo "App Dir   : ${APP_DIR}"
echo "Servicio  : ${SERVICE_NAME}"
echo
echo "Comandos útiles:"
echo "  • Iniciar ahora        : sudo systemctl start ${SERVICE_NAME}"
echo "  • Ver logs del servicio: journalctl -u ${SERVICE_NAME} -f"
echo "  • Ejecutar manual (X)  : startx  (o)  xinit /usr/local/bin/bascula-xsession -- :0 vt1 -nocursor"
echo "  • Probar cámara Python : python3 -c 'from picamera2 import Picamera2; Picamera2(); print(\"OK\")'"
echo
echo "Reinicia para aplicar HDMI/UART por completo:  sudo reboot"

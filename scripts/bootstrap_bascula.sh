#!/usr/bin/env bash
# ==============================================================================
# scripts/bootstrap_bascula.sh  —  Setup sin AP (Wi-Fi de casa únicamente)
# Raspberry Pi OS Bookworm 64-bit  ·  Raspberry Pi Zero 2 W
# Proyecto: bascula-cam
#
# Qué hace:
# - dpkg/apt al día
# - Instala paquetes base (LightDM, Xorg, NetworkManager, Picamera2…)
# - Configura autologin LightDM para usuario 'bascula'
# - Copia desde el repo los servicios systemd (UI y mini-web, si existen)
# - Ajusta HDMI 1024x600 (KMS) y UART (/dev/serial0) idempotente
# - NO crea AP ni dispatcher. Respeta la Wi-Fi existente (no la toca).
#
# Requisitos previos:
# 1) Haber creado el usuario 'bascula' (sin contraseña si quieres):
#      sudo adduser --disabled-password --gecos "Bascula" bascula
#      sudo usermod -aG bascula,tty,dialout,video,gpio bascula
# 2) Tener clave SSH añadida en GitHub y repo clonado en:
#      /home/bascula/bascula-cam
#
# Uso:
#   sudo bash /home/bascula/bascula-cam/scripts/bootstrap_bascula.sh
# ==============================================================================

set -euo pipefail

# --- Paths del repo (asumimos que ejecutas este script desde el repo clonado) ---
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYSTEMD_DIR="${REPO_ROOT}/systemd"
POLKIT_SRC_DIR="${REPO_ROOT}/polkit"   # opcional (solo si lo usas)
# Si no necesitas polkit para NM, puedes ignorar esa carpeta.

# --- Archivos destino del sistema ---
UI_SERVICE_DST="/etc/systemd/system/bascula-ui.service"
WEB_SERVICE_DST="/etc/systemd/system/bascula-web.service"  # si existe en el repo, lo copiaremos

# Bookworm vs Bullseye (paths de /boot)
BOOT_FW_DIR="/boot/firmware"
CONFIG_TXT="${BOOT_FW_DIR}/config.txt"
CMDLINE_TXT="${BOOT_FW_DIR}/cmdline.txt"
if [[ ! -d "${BOOT_FW_DIR}" ]]; then
  BOOT_FW_DIR="/boot"
  CONFIG_TXT="${BOOT_FW_DIR}/config.txt"
  CMDLINE_TXT="${BOOT_FW_DIR}/cmdline.txt"
fi

BASCULA_USER="bascula"
BASCULA_HOME="/home/${BASCULA_USER}"
REPO_DIR="${BASCULA_HOME}/bascula-cam"

# ---------------------- Helpers ----------------------
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
  # Añade la línea sólo si no existe exacta en el fichero:
  grep -qxF "$line" "$file" 2>/dev/null || echo "$line" >> "$file"
}

# ---------------------- Inicio -----------------------
require_root

log "1) dpkg y sistema al día…"
dpkg --configure -a || true
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get full-upgrade -y

log "2) Paquetes base (Xorg/LightDM/NM/Picamera2)…"
# ¡OJO! Sin 'wiringpi' (obsoleto en Bookworm)
apt-get install -y \
  xserver-xorg lightdm lightdm-gtk-greeter \
  network-manager policykit-1 \
  python3-venv python3-pip \
  rpicam-apps python3-picamera2 \
  git curl nano raspi-config

log "3) Verificando usuario '${BASCULA_USER}' y grupos…"
id "${BASCULA_USER}" >/dev/null 2>&1 || { err "Falta usuario '${BASCULA_USER}'. Crea primero el usuario y su SSH."; exit 1; }
usermod -aG "${BASCULA_USER},tty,dialout,video,gpio" "${BASCULA_USER}" || true

log "4) LightDM autologin a '${BASCULA_USER}'…"
mkdir -p /etc/lightdm/lightdm.conf.d
cat > /etc/lightdm/lightdm.conf.d/50-bascula-autologin.conf <<'EOF'
[Seat:*]
autologin-user=bascula
autologin-user-timeout=0
user-session=lightdm-autologin
EOF
systemctl enable --now lightdm.service

log "5) Copiar servicios systemd desde el repo…"
# UI (OBLIGATORIO para este flujo)
if [[ -f "${SYSTEMD_DIR}/bascula-ui.service" ]]; then
  install -m 0644 "${SYSTEMD_DIR}/bascula-ui.service" "${UI_SERVICE_DST}"
  systemctl daemon-reload
  systemctl enable --now bascula-ui.service
else
  warn "No existe ${SYSTEMD_DIR}/bascula-ui.service en el repo. La UI no arrancará."
fi

# Mini-web (OPCIONAL: lo copiamos si lo tienes en el repo)
if [[ -f "${SYSTEMD_DIR}/bascula-web.service" ]]; then
  install -m 0644 "${SYSTEMD_DIR}/bascula-web.service" "${WEB_SERVICE_DST}"
  systemctl daemon-reload
  systemctl enable --now bascula-web.service || warn "No se pudo iniciar bascula-web.service (ver logs)."
else
  warn "No existe ${SYSTEMD_DIR}/bascula-web.service en el repo. Saltando mini-web."
fi

log "6) HDMI 1024x600 (KMS) en ${CONFIG_TXT} (idempotente)…"
touch "${CONFIG_TXT}"
# Evitar duplicados de dtoverlay:
sed -i '/^dtoverlay=vc4-kms-v3d/d' "${CONFIG_TXT}" || true
append_once "dtoverlay=vc4-kms-v3d" "${CONFIG_TXT}"
append_once "hdmi_force_hotplug=1" "${CONFIG_TXT}"
append_once "hdmi_group=2" "${CONFIG_TXT}"
append_once "hdmi_mode=87" "${CONFIG_TXT}"
append_once "hdmi_cvt=1024 600 60 3 0 0 0" "${CONFIG_TXT}"

log "7) UART libre (/dev/serial0) y sin consola serie…"
touch "${CMDLINE_TXT}"
# Quitar 'console=serial0,115200' si estuviera:
sed -i 's/console=serial0,[0-9]* //g' "${CMDLINE_TXT}" || true
# En config.txt, asegurar enable_uart y disable-bt (idempotente):
sed -i '/^enable_uart=/d' "${CONFIG_TXT}" || true
sed -i '/^dtoverlay=disable-bt/d' "${CONFIG_TXT}" || true
append_once "enable_uart=1" "${CONFIG_TXT}"
append_once "dtoverlay=disable-bt" "${CONFIG_TXT}"

log "8) Respetando tu Wi-Fi actual: no se toca configuración de SSID/clave."
# Sólo reiniciamos NetworkManager para que recoja cualquier cambio de systemd/polkit si existiera.
systemctl restart NetworkManager || true

log "9) Comprobaciones rápidas…"
if [[ -e /dev/serial0 ]]; then
  log "   UART OK: /dev/serial0 presente"
else
  warn "   UART aún no visible (se aplicará tras reboot)."
fi

if command -v rpicam-hello >/dev/null 2>&1; then
  log "   rpicam-hello OK (prueba: rpicam-hello --list-cameras)"
fi

log "10) Reiniciando para aplicar KMS/HDMI/UART…"
sleep 2
reboot

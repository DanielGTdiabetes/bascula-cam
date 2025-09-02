#!/usr/bin/env bash
# ==============================================================================
# scripts/bootstrap_bascula.sh
# Setup integral para Raspberry Pi Zero 2 W (Raspberry Pi OS Bookworm, 64-bit)
# Proyecto: bascula-cam
#
# Qué hace:
# - Sistema al día, paquetes base (Xorg/LightDM, NM, Picamera2, etc.)
# - LightDM + servicio UI (bascula-ui.service) -> copiado desde el repo
# - HDMI 1024x600 KMS (sin duplicados; idempotente)
# - UART libre (/dev/serial0) y sin consola serie
# - Polkit NM -> copiado desde el repo
# - AP BasculaAP y dispatcher fallback -> copiado desde el repo
# - NO toca tu Wi-Fi de casa si ya existe/está activa (lo respeta)
# ==============================================================================

set -euo pipefail

# --- Paths repo (asumimos que ejecutas desde el propio repo) ---
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYSTEMD_DIR="${REPO_ROOT}/systemd"
DISPATCHER_SRC_DIR="${REPO_ROOT}/scripts/nm-dispatcher"
POLKIT_SRC_DIR="${REPO_ROOT}/polkit"

# --- Archivos destino del sistema ---
UI_SERVICE_DST="/etc/systemd/system/bascula-ui.service"
DISPATCHER_DST_DIR="/etc/NetworkManager/dispatcher.d"
POLKIT_RULE_DST="/etc/polkit-1/rules.d/50-bascula-nm.rules"

# Bookworm paths
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

log()  { printf "\n\033[1;32m[bootstrap]\033[0m %s\n" "$*"; }
warn() { printf "\n\033[1;33m[bootstrap-warning]\033[0m %s\n" "$*"; }
err()  { printf "\n\033[1;31m[bootstrap-error]\033[0m %s\n" "$*" 1>&2; }

require_root() {
  if [[ $EUID -ne 0 ]]; then
    err "Ejecuta como root: sudo bash scripts/bootstrap_bascula.sh"
    exit 1
  fi
}

append_once() {
  local line="$1" file="$2"
  grep -qxF "$line" "$file" 2>/dev/null || echo "$line" >> "$file"
}

wifi_is_active() {
  # Devuelve 0 si NM reporta wifi 'connected' con IP (modo infrastructure)
  local active_con mode
  active_con=$(nmcli -t -f TYPE,STATE,CONNECTION device status | awk -F: '$1=="wifi" && $2=="connected"{print $3}')
  if [[ -n "${active_con}" ]]; then
    mode=$(nmcli -t -f 802-11-wireless.mode connection show "${active_con}" 2>/dev/null | awk -F: 'NR==1{print $1}')
    [[ "${mode}" != "ap" ]] && return 0
  fi
  return 1
}

require_root

log "1) dpkg y sistema al día…"
dpkg --configure -a || true
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get full-upgrade -y

log "2) Paquetes base (Xorg/LightDM/NM/Picamera2)…"
apt-get install -y \
  xserver-xorg lightdm lightdm-gtk-greeter \
  network-manager policykit-1 \
  python3-venv python3-pip \
  rpicam-apps python3-picamera2 \
  git curl nano wiringpi raspi-config

log "3) Verificando usuario '${BASCULA_USER}' y grupos…"
id "${BASCULA_USER}" >/dev/null 2>&1 || err "Falta usuario '${BASCULA_USER}'. Crea primero el usuario y su SSH (ver paso 0)."
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

log "5) Copiando unidad UI desde el repo → ${UI_SERVICE_DST}"
[[ -f "${SYSTEMD_DIR}/bascula-ui.service" ]] || err "No existe ${SYSTEMD_DIR}/bascula-ui.service en el repo."
install -m 0644 "${SYSTEMD_DIR}/bascula-ui.service" "${UI_SERVICE_DST}"
systemctl daemon-reload
systemctl enable --now bascula-ui.service

log "6) Reglas polkit (desde repo) → ${POLKIT_RULE_DST}"
[[ -f "${POLKIT_SRC_DIR}/50-bascula-nm.rules" ]] || err "No existe ${POLKIT_SRC_DIR}/50-bascula-nm.rules en el repo."
install -m 0644 "${POLKIT_SRC_DIR}/50-bascula-nm.rules" "${POLKIT_RULE_DST}"
systemctl restart polkit || true
systemctl restart NetworkManager || true

log "7) HDMI 1024x600 KMS en ${CONFIG_TXT} (idempotente)…"
touch "${CONFIG_TXT}"
sed -i '/^dtoverlay=vc4-kms-v3d/d' "${CONFIG_TXT}" || true
append_once "dtoverlay=vc4-kms-v3d" "${CONFIG_TXT}"
append_once "hdmi_force_hotplug=1" "${CONFIG_TXT}"
append_once "hdmi_group=2" "${CONFIG_TXT}"
append_once "hdmi_mode=87" "${CONFIG_TXT}"
append_once "hdmi_cvt=1024 600 60 3 0 0 0" "${CONFIG_TXT}"

log "8) UART libre (/dev/serial0) y sin consola en ${CMDLINE_TXT}…"
touch "${CMDLINE_TXT}"
sed -i 's/console=serial0,[0-9]* //g' "${CMDLINE_TXT}" || true
sed -i '/^enable_uart=/d' "${CONFIG_TXT}" || true
sed -i '/^dtoverlay=disable-bt/d' "${CONFIG_TXT}" || true
append_once "enable_uart=1" "${CONFIG_TXT}"
append_once "dtoverlay=disable-bt" "${CONFIG_TXT}"

log "9) Wi-Fi: respetar perfil ACTIVO (no tocar). Solo crear AP y dispatcher."
if wifi_is_active; then
  log "   Wi-Fi activa detectada. No se modifican perfiles de casa."
else
  log "   No hay Wi-Fi activa ahora mismo: igualmente NO se crea perfil de casa (regla: no tocar)."
fi

log "10) Crear/actualizar AP 'BasculaAP' y dispatcher (desde repo)…"
# Crear AP si falta (no autoconnect por defecto)
nmcli connection show "BasculaAP" >/dev/null 2>&1 || \
nmcli connection add type wifi ifname wlan0 con-name "BasculaAP" autoconnect no ssid "BasculaAP"
nmcli connection modify "BasculaAP" 802-11-wireless.mode ap 802-11-wireless.band bg ipv4.method shared ipv6.method ignore
nmcli connection modify "BasculaAP" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "Bascula1234"

# Dispatcher desde el repo
install -d "${DISPATCHER_DST_DIR}"
[[ -f "${DISPATCHER_SRC_DIR}/90-bascula-ap-fallback" ]] || err "No existe ${DISPATCHER_SRC_DIR}/90-bascula-ap-fallback en el repo."
install -m 0755 "${DISPATCHER_SRC_DIR}/90-bascula-ap-fallback" "${DISPATCHER_DST_DIR}/90-bascula-ap-fallback"
systemctl restart NetworkManager || true

log "11) Comprobaciones rápidas…"
[[ -e /dev/serial0 ]] && log "   UART OK: /dev/serial0 presente" || warn "   UART NO encontrado (se aplicará tras reboot)."
command -v rpicam-hello >/dev/null && log "   rpicam-hello OK (prueba cámara con: rpicam-hello --list-cameras)"

log "12) Reiniciando para aplicar KMS/HDMI/UART…"
sleep 2
reboot

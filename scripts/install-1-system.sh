#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
MARKER="/var/lib/bascula/install-1.done"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  TARGET_USER="${TARGET_USER:-$(id -un)}"
  exec sudo TARGET_USER="${TARGET_USER}" bash "$0" "$@"
fi

TARGET_USER="${TARGET_USER:-${SUDO_USER:-pi}}"

echo "[install-1-system] Preparando sistema base"

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y network-manager
systemctl enable NetworkManager
systemctl restart NetworkManager

# Polkit para permitir shared/system changes al grupo netdev
if [[ -f "${ROOT_DIR}/scripts/polkit/10-nm-shared.pkla" ]]; then
  install -m 0644 -o root -g root "${ROOT_DIR}/scripts/polkit/10-nm-shared.pkla" \
    /etc/polkit-1/localauthority/50-local.d/10-nm-shared.pkla
  usermod -aG netdev "${TARGET_USER}"
fi

echo "[install-1-system] Instalando dependencias base"
apt-get install -y \
  xserver-xorg x11-xserver-utils xinit xserver-xorg-legacy unclutter \
  libcamera-apps v4l-utils python3-picamera2

if ! getent group render >/dev/null 2>&1; then
  groupadd --system render
fi
usermod -aG video,render,input "${TARGET_USER}" || true

install -D -m 0644 /dev/null /etc/Xwrapper.config
cat > /etc/Xwrapper.config <<'EOF'
allowed_users=anybody
needs_root_rights=yes
EOF

install -D -m 0644 "${ROOT_DIR}/packaging/tmpfiles/bascula-x11.conf" /etc/tmpfiles.d/bascula-x11.conf
systemd-tmpfiles --create /etc/tmpfiles.d/bascula-x11.conf || true

install -D -m 0644 /dev/null /etc/default/rpi-eeprom-update
cat > /etc/default/rpi-eeprom-update <<'EOF'
FIRMWARE_RELEASE_STATUS="critical"
EOF
apt-get install -y rpi-eeprom
apt-mark hold rpi-eeprom >/dev/null 2>&1 || true

echo "[install-1-system] Ejecutando fase 1 del instalador principal"
SKIP_INSTALL_ALL_PACKAGES=1 \
SKIP_INSTALL_ALL_GROUPS=1 \
SKIP_INSTALL_ALL_XWRAPPER=1 \
SKIP_INSTALL_ALL_X11_TMPFILES=1 \
SKIP_INSTALL_ALL_EEPROM_CONFIG=1 \
PHASE=1 TARGET_USER="${TARGET_USER}" bash "${SCRIPT_DIR}/install-all.sh" "$@"

install -d -m 0755 /var/lib/bascula
install -o root -g root -m 0644 /dev/null "${MARKER}"

echo "[install-1-system] Parte 1 completada, reinicia ahora"

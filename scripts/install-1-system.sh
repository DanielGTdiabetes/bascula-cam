#!/usr/bin/env bash
: "${TARGET_USER:=pi}"
: "${FORCE_INSTALL_PACKAGES:=0}"

set -euxo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
MARKER="/var/lib/bascula/install-1.done"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  exec sudo TARGET_USER="${TARGET_USER}" FORCE_INSTALL_PACKAGES="${FORCE_INSTALL_PACKAGES}" bash "$0" "$@"
fi

TARGET_USER="${TARGET_USER:-${SUDO_USER:-pi}}"
TARGET_GROUP="$(id -gn "${TARGET_USER}" 2>/dev/null || echo "${TARGET_USER}")"
export DEBIAN_FRONTEND=noninteractive

# Parte 1 SIEMPRE instala paquetes base en limpias
# (no usar SKIP_INSTALL_ALL_PACKAGES aquí)
apt-get update

# Paquetes base del sistema (toolchain, python build, OCR, X, cámara, audio, red, utilidades)
DEPS=(
  # UI/X
  xserver-xorg x11-xserver-utils xinit xserver-xorg-legacy unclutter python3-tk
  mesa-utils libegl1 libgles2 fonts-dejavu fonts-freefont-ttf
  # Cámara
  libcamera-apps python3-picamera2 v4l-utils
  # Audio
  alsa-utils
  # OCR / visión
  tesseract-ocr libtesseract-dev libleptonica-dev tesseract-ocr-spa tesseract-ocr-eng
  # ZBar (QR/Barcodes si la app lo usa)
  libzbar0 zbar-tools
  # Python build
  python3-venv python3-pip python3-dev build-essential libffi-dev zlib1g-dev \
  libjpeg-dev libopenjp2-7 libtiff5 libatlas-base-dev
  # Red
  network-manager rfkill
  # Miscelánea / CLI
  curl git jq usbutils pciutils rsync
  # EEPROM (bloqueada en critical)
  rpi-eeprom
)

apt-get install -y "${DEPS[@]}"

systemctl enable NetworkManager || true
systemctl restart NetworkManager || true

# Reglas Polkit para permitir gestión de Wi-Fi y servicios Bascula
install -d -m 0755 /etc/polkit-1/rules.d
cat > /etc/polkit-1/rules.d/50-bascula-nm.rules <<EOF
polkit.addRule(function(action, subject) {
  function allowed() {
    return subject.user == "${TARGET_USER}" || subject.isInGroup("${TARGET_GROUP}");
  }
  if (!allowed()) return polkit.Result.NOT_HANDLED;

  const id = action.id;
  if (id == "org.freedesktop.NetworkManager.settings.modify.system" ||
      id == "org.freedesktop.NetworkManager.network-control" ||
      id == "org.freedesktop.NetworkManager.enable-disable-wifi") {
    return polkit.Result.YES;
  }
});
EOF
cat > /etc/polkit-1/rules.d/51-bascula-systemd.rules <<EOF
polkit.addRule(function(action, subject) {
  var id = action.id;
  var unit = action.lookup("unit") || "";
  function allowedUnit(u) {
    return typeof u === "string" && u.indexOf("bascula-") === 0;
  }
  if ((subject.user == "${TARGET_USER}" || subject.isInGroup("${TARGET_GROUP}")) &&
      (id == "org.freedesktop.systemd1.manage-units" ||
       id == "org.freedesktop.systemd1.restart-unit" ||
       id == "org.freedesktop.systemd1.start-unit" ||
       id == "org.freedesktop.systemd1.stop-unit") &&
      allowedUnit(unit)) {
    return polkit.Result.YES;
  }
});
EOF
systemctl restart polkit NetworkManager || true

# Polkit para permitir shared/system changes al grupo netdev
if [[ -f "${ROOT_DIR}/scripts/polkit/10-nm-shared.pkla" ]]; then
  install -m 0644 -o root -g root "${ROOT_DIR}/scripts/polkit/10-nm-shared.pkla" \
    /etc/polkit-1/localauthority/50-local.d/10-nm-shared.pkla
  usermod -aG netdev "${TARGET_USER}" || true
fi

# Xwrapper: permitir X como usuario normal
install -D -m 0644 /dev/null /etc/Xwrapper.config
cat >/etc/Xwrapper.config <<'EOCONF'
allowed_users=anybody
needs_root_rights=yes
EOCONF

# tmpfiles: socket X por boot
install -D -m 0644 "${SCRIPT_DIR}/../packaging/tmpfiles/bascula-x11.conf" /etc/tmpfiles.d/bascula-x11.conf
systemd-tmpfiles --create /etc/tmpfiles.d/bascula-x11.conf || true

# Grupos: GPU/entrada
getent group render >/dev/null || groupadd render
usermod -aG video,render,input "${TARGET_USER}" || true

# EEPROM conservadora
install -D -m 0644 /dev/null /etc/default/rpi-eeprom-update
cat >/etc/default/rpi-eeprom-update <<'EOEEPROM'
FIRMWARE_RELEASE_STATUS="critical"
EOEEPROM
apt-mark hold rpi-eeprom || true

# (P1) Configurar AP de NetworkManager ahora para permitir onboarding tras Fase 1
bash "${SCRIPT_DIR}/setup_ap_nm.sh" || true

# Marca de fin de parte 1
install -d -m 0755 /var/lib/bascula
echo ok > "${MARKER}"
echo "[INFO] Parte 1 completada. Reinicia ahora."

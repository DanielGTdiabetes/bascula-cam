#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  TARGET_USER="${TARGET_USER:-$(id -un)}"
  exec sudo TARGET_USER="${TARGET_USER}" bash "$0" "$@"
fi

TARGET_USER="${TARGET_USER:-${SUDO_USER:-pi}}"

# Asegura NetworkManager
sudo apt-get update -y
sudo apt-get install -y network-manager
sudo systemctl enable NetworkManager
sudo systemctl restart NetworkManager

# Polkit para permitir shared/system changes al grupo netdev
if [[ -f "${ROOT_DIR}/scripts/polkit/10-nm-shared.pkla" ]]; then
  sudo install -m 0644 -o root -g root "${ROOT_DIR}/scripts/polkit/10-nm-shared.pkla" \
    /etc/polkit-1/localauthority/50-local.d/10-nm-shared.pkla
  sudo usermod -aG netdev "${TARGET_USER}"
fi

# Resto de instalación principal
PHASE=1 TARGET_USER="${TARGET_USER}" bash "${SCRIPT_DIR}/install-all.sh" "$@"

# Configura y levanta AP con NM (idempotente)
bash "${ROOT_DIR}/scripts/setup_ap_nm.sh"

# Verificación resumida
nmcli -t -f DEVICE,TYPE,STATE,CONNECTION dev || true
ip -4 -o addr show | sed -n '1,200p' || true
echo "[install-1-system] OK"

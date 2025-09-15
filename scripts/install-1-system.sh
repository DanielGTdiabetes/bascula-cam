#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

log(){ echo "[$1] ${2:-}"; }
die(){ log ERR "${1}"; exit 1; }

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  die "Este script debe ejecutarse con sudo o como root"
fi

TARGET_USER="${TARGET_USER:-${SUDO_USER:-pi}}"
if ! id "${TARGET_USER}" >/dev/null 2>&1; then
  die "El usuario objetivo '${TARGET_USER}' no existe"
fi
TARGET_GROUP="$(id -gn "${TARGET_USER}")"

log INFO "Instalando dependencias del sistema para ${TARGET_USER}"
export DEBIAN_FRONTEND=noninteractive
apt-get update
APT_PACKAGES=(
  git curl ca-certificates build-essential cmake pkg-config
  python3 python3-venv python3-pip python3-tk python3-numpy python3-serial 'python3-pil.imagetk'
  x11-xserver-utils xserver-xorg xinit openbox unclutter fonts-dejavu
  libjpeg-dev zlib1g-dev libpng-dev
  alsa-utils sox ffmpeg
  libzbar0 gpiod python3-rpi.gpio
  network-manager sqlite3 tesseract-ocr tesseract-ocr-spa espeak-ng
  patchelf
)
apt-get install -y "${APT_PACKAGES[@]}"

CONFIG_FILE="/boot/firmware/config.txt"
if [[ ! -f "${CONFIG_FILE}" ]]; then
  CONFIG_FILE="/boot/config.txt"
fi
if [[ ! -f "${CONFIG_FILE}" ]]; then
  die "No se encontró config.txt ni en /boot/firmware ni en /boot"
fi

ensure_overlay(){
  local line="$1"
  if grep -Fxq "${line}" "${CONFIG_FILE}"; then
    log INFO "${line} ya presente en ${CONFIG_FILE}"
  else
    printf '%s\n' "${line}" >> "${CONFIG_FILE}"
    log INFO "Añadido ${line} a ${CONFIG_FILE}"
  fi
}
ensure_overlay "dtoverlay=audremap,pins_18_19"
ensure_overlay "dtoverlay=hifiberry-dac"

for group in audio video input; do
  if id -nG "${TARGET_USER}" | tr ' ' '\n' | grep -Fxq "${group}"; then
    log INFO "${TARGET_USER} ya pertenece al grupo ${group}"
  else
    usermod -aG "${group}" "${TARGET_USER}"
    log INFO "Añadido ${TARGET_USER} al grupo ${group}"
  fi
done

log INFO "Fase 1 completada. Ejecuta install-2-app.sh para continuar con la aplicación"

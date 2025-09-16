#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

log(){ echo "[$1] ${2:-}"; }
die(){ log ERR "${1}"; exit 1; }

usage(){
  cat <<'USAGE'
Uso: install-1-system.sh [--only-polkit] [--only-uart]
  --only-polkit  Ejecuta únicamente la configuración de Polkit
  --only-uart    Ejecuta únicamente la configuración de UART
USAGE
  exit "${1:-0}"
}

POLKIT_ONLY=false
UART_ONLY=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --only-polkit)
      POLKIT_ONLY=true
      ;;
    --only-uart)
      UART_ONLY=true
      ;;
    -h|--help)
      usage 0
      ;;
    *)
      log ERR "Opción no reconocida: $1"
      usage 1
      ;;
  esac
  shift
done

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  die "Este script debe ejecutarse con sudo o como root"
fi

TARGET_USER="${TARGET_USER:-pi}"

DO_CORE=false
DO_POLKIT=false
DO_UART=false
if [[ "${POLKIT_ONLY}" == "true" && "${UART_ONLY}" == "true" ]]; then
  DO_POLKIT=true
  DO_UART=true
elif [[ "${POLKIT_ONLY}" == "true" ]]; then
  DO_POLKIT=true
elif [[ "${UART_ONLY}" == "true" ]]; then
  DO_UART=true
else
  DO_CORE=true
  DO_POLKIT=true
  DO_UART=true
fi

ensure_target_user(){
  if ! id -u "${TARGET_USER}" >/dev/null 2>&1; then
    log INFO "Creando usuario ${TARGET_USER}"
    useradd -m -s /bin/bash "${TARGET_USER}"
  fi
}

ensure_polkit(){
  ensure_target_user

  local rules_dir="/etc/polkit-1/rules.d"
  local rule_file="${rules_dir}/45-bascula-nm.rules"

  install -d -m 0755 "${rules_dir}"
  chown root:root "${rules_dir}"

  if [[ -f "${rule_file}" ]] && grep -q 'org.freedesktop.NetworkManager.network-control' "${rule_file}"; then
    :
  else
    cat <<'RULE' > "${rule_file}"
// 45-bascula-nm.rules — permitir nmcli a grupo netdev
polkit.addRule(function(action, subject) {
  const ids = [
    "org.freedesktop.NetworkManager.network-control",
    "org.freedesktop.NetworkManager.settings.modify.system",
    "org.freedesktop.NetworkManager.settings.modify.own",
    "org.freedesktop.NetworkManager.settings.modify.hostname"
  ];
  if (ids.indexOf(action.id) >= 0 && subject.isInGroup("netdev")) {
    return polkit.Result.YES;
  }
});
RULE
  fi

  chmod 0644 "${rule_file}"
  chown root:root "${rule_file}"

  if ! id -nG "${TARGET_USER}" | tr ' ' '\n' | grep -Fxq netdev; then
    usermod -aG netdev "${TARGET_USER}"
  fi

  systemctl restart polkit 2>/dev/null || systemctl restart polkitd 2>/dev/null || true
  log polkit "reglas instaladas y grupo netdev aplicado a ${TARGET_USER}"
}

configure_uart(){
  local conf="/boot/firmware/config.txt"
  [[ -f "${conf}" ]] || conf="/boot/config.txt"
  if [[ ! -f "${conf}" ]]; then
    die "No se encontró config.txt ni en /boot/firmware ni en /boot"
  fi

  local conf_changed=false
  if grep -qE '^\s*enable_uart\s*=\s*1\s*$' "${conf}"; then
    :
  else
    echo 'enable_uart=1' >> "${conf}"
    conf_changed=true
  fi
  log uart "enable_uart=1 presente en ${conf}"

  local cmdline="/boot/firmware/cmdline.txt"
  [[ -f "${cmdline}" ]] || cmdline="/boot/cmdline.txt"
  if [[ ! -f "${cmdline}" ]]; then
    die "No se encontró cmdline.txt ni en /boot/firmware ni en /boot"
  fi

  local cmdline_changed=false
  if grep -q 'console=serial0' "${cmdline}"; then
    sed -i -E 's/\s*console=serial0,[0-9]+//g' "${cmdline}"
    cmdline_changed=true
    log uart "console=serial0 eliminado de ${cmdline}"
  else
    log uart "console=serial0 no presente en ${cmdline}"
  fi

  if [[ "${conf_changed}" == "true" || "${cmdline_changed}" == "true" ]]; then
    log uart "Se recomienda reiniciar la Raspberry Pi para aplicar los cambios de UART"
  fi
}

if [[ "${DO_CORE}" == "true" || "${DO_POLKIT}" == "true" ]]; then
  ensure_target_user
fi

if [[ "${DO_CORE}" == "true" ]]; then
  log INFO "Instalando dependencias del sistema para ${TARGET_USER}"
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  APT_PACKAGES=(
    git curl ca-certificates rsync build-essential cmake pkg-config
    python3 python3-venv python3-pip python3-tk python3-numpy python3-serial 'python3-pil.imagetk'
    x11-xserver-utils xserver-xorg xinit openbox unclutter fonts-dejavu
    libjpeg-dev zlib1g-dev libpng-dev
    alsa-utils sox ffmpeg
    libzbar0 gpiod python3-rpi.gpio
    network-manager sqlite3 tesseract-ocr tesseract-ocr-spa espeak-ng espeak-ng-data
    patchelf jq
  )
  apt-get install -y "${APT_PACKAGES[@]}"
  if dpkg -s espeak-ng-data >/dev/null 2>&1; then
    log espeak "espeak-ng-data instalado"
  else
    log espeak "espeak-ng-data no se pudo instalar"
  fi

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
fi

if [[ "${DO_POLKIT}" == "true" ]]; then
  ensure_polkit
fi

if [[ "${DO_UART}" == "true" ]]; then
  configure_uart
fi

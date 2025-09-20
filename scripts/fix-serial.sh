#!/usr/bin/env bash
set -euo pipefail

log()  { printf "\033[1;34m[serial]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[serial]\033[0m %s\n" "$*"; }

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  warn "Se requieren privilegios de root"
  exec sudo TARGET_USER="${TARGET_USER:-}" "$0" "$@"
fi

TARGET_USER="${TARGET_USER:-${SUDO_USER:-pi}}"
if ! id "${TARGET_USER}" &>/dev/null; then
  warn "Usuario ${TARGET_USER} no encontrado, usando 'pi'"
  TARGET_USER="pi"
fi

log "Ajustando grupos para ${TARGET_USER}"
usermod -aG dialout "${TARGET_USER}" || true
usermod -aG tty "${TARGET_USER}" || true

RULE_FILE="/etc/udev/rules.d/90-bascula.rules"
if [[ ! -f "${RULE_FILE}" ]]; then
  log "Creando reglas udev en ${RULE_FILE}"
else
  log "Actualizando reglas udev en ${RULE_FILE}"
fi
cat <<'EOF' > "${RULE_FILE}"
# Bascula-Cam serial access rules
KERNEL=="ttyAMA0", MODE="0660", GROUP="dialout"
KERNEL=="ttyS0",   MODE="0660", GROUP="dialout"
SUBSYSTEM=="tty", MODE="0660", GROUP="dialout"
EOF

udevadm control --reload-rules && udevadm trigger || true

BOOTDIR="/boot/firmware"
[[ -d "${BOOTDIR}" ]] || BOOTDIR="/boot"
CMDLINE="${BOOTDIR}/cmdline.txt"
CONFIG="${BOOTDIR}/config.txt"

if [[ -f "${CMDLINE}" ]]; then
  log "Limpiando consola serie de ${CMDLINE}"
  sed -i 's/console=serial0,115200 //g; s/console=ttyAMA0,115200 //g' "${CMDLINE}" || true
fi

if [[ -f "${CONFIG}" ]]; then
  if ! grep -q '^enable_uart=1' "${CONFIG}"; then
    log "Habilitando UART en ${CONFIG}"
    printf '\nenable_uart=1\n' >> "${CONFIG}"
  else
    log "UART ya habilitado en ${CONFIG}"
  fi
fi

if command -v raspi-config >/dev/null 2>&1; then
  log "raspi-config: deshabilitando consola serie"
  raspi-config nonint do_serial 2 || true
fi

if [[ -e /dev/serial0 ]]; then
  stty -F /dev/serial0 115200 -echo -icrnl -ixon -opost raw || true
fi

log "Correcciones de puerto serie aplicadas"

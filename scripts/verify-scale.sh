#!/usr/bin/env bash
set -euo pipefail

TARGET_USER="${TARGET_USER:-pi}"
USER_HOME="${TARGET_HOME:-/home/${TARGET_USER}}"
APP_DIR="${APP_DIR:-${USER_HOME}/bascula-cam}"
UDEV_RULE="/etc/udev/rules.d/99-scale.rules"

log() { printf '[inst] %s\n' "$*"; }
ok() { printf '[ok] %s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*"; }

log "Verificando grupos de ${TARGET_USER}"
if id -u "${TARGET_USER}" >/dev/null 2>&1; then
  id "${TARGET_USER}" | sed 's/^/[ok] /'
else
  warn "Usuario ${TARGET_USER} no existe"
fi

log "Dispositivos serie/I2C disponibles"
shopt -s nullglob
found=false
for path in /dev/ttyACM* /dev/ttyUSB* /dev/i2c*; do
  if [[ -e "${path}" ]]; then
    found=true
    ls -l "${path}" | sed 's/^/[ok] /'
  fi
done
shopt -u nullglob
if [[ "${found}" == false ]]; then
  warn "No se encontraron dispositivos /dev/ttyACM* /dev/ttyUSB* /dev/i2c*"
fi

log "Regla udev"
if [[ -f "${UDEV_RULE}" ]]; then
  sed 's/^/[ok] /' "${UDEV_RULE}"
else
  warn "No existe ${UDEV_RULE}"
fi

log "Configuración BASCULA_DEVICE"
if [[ -f /etc/bascula/bascula.env ]]; then
  grep -E '^#?BASCULA_DEVICE' /etc/bascula/bascula.env | sed 's/^/[ok] /' || true
else
  warn "/etc/bascula/bascula.env no encontrado"
fi

PYTHON_BIN="${APP_DIR}/.venv/bin/python"
if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python3"
fi

if [[ -f "${APP_DIR}/tools/check_scale.py" ]]; then
  log "Ejecutando check_scale"
  if sudo -u "${TARGET_USER}" -H "${PYTHON_BIN}" "${APP_DIR}/tools/check_scale.py"; then
    ok "check_scale completado"
  else
    warn "check_scale reportó problemas"
  fi
else
  warn "tools/check_scale.py no encontrado"
fi

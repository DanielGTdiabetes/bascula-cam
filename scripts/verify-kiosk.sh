#!/usr/bin/env bash
set -euo pipefail

TARGET_USER="${TARGET_USER:-pi}"
TARGET_HOME="${TARGET_HOME:-/home/${TARGET_USER}}"
APP_DIR="${APP_DIR:-${TARGET_HOME}/bascula-cam}"
VENV_PY="${APP_DIR}/.venv/bin/python"
PIP_CACHE="${TARGET_HOME}/.cache/pip"
MODELS_DIR="/opt/piper/models"

log() { printf '[inst] %s\n' "$*"; }
ok() { printf '[ok] %s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*"; }

log "Pantalla X"
if [[ -S /tmp/.X11-unix/X0 ]]; then
  ok "Socket X0 disponible"
else
  warn "No se detecta /tmp/.X11-unix/X0"
fi

if [[ -n "${DISPLAY:-}" ]]; then
  log "Mascota"
  if python3 "${APP_DIR}/tools/smoke_mascot.py" >/dev/null 2>&1; then
    ok "Smoke de mascot sin errores"
  else
    warn "Smoke de mascot falló"
  fi
else
  warn "DISPLAY no definido, se omite smoke de mascota"
fi

if command -v startx >/dev/null 2>&1; then
  ok "startx presente"
else
  warn "startx no encontrado"
fi

log "Servicios systemd"
if systemctl list-units --type=service --all | grep -q '^bascula-miniweb.service'; then
  if systemctl is-active bascula-miniweb.service >/dev/null 2>&1; then
    ok "bascula-miniweb activo"
  else
    warn "bascula-miniweb no activo"
  fi
else
  warn "bascula-miniweb.service no existe"
fi

if systemctl list-units --type=service --all | grep -q '^x735-fan.service'; then
  if systemctl is-active x735-fan.service >/dev/null 2>&1; then
    ok "x735-fan activo"
  else
    warn "x735-fan inactivo"
  fi
else
  warn "x735-fan.service no existe"
fi

if systemctl list-units --type=service --all | grep -q '^bascula-ui.service'; then
  env_info=$(systemctl show bascula-ui.service -p Environment 2>/dev/null || true)
  if grep -q 'DISPLAY=:0' <<<"${env_info}"; then
    ok "bascula-ui con DISPLAY=:0"
  else
    warn "bascula-ui sin DISPLAY=:0"
  fi
  if grep -q 'XAUTHORITY=' <<<"${env_info}"; then
    ok "bascula-ui con XAUTHORITY"
  else
    warn "bascula-ui sin XAUTHORITY"
  fi
else
  warn "bascula-ui.service no existe"
fi

log "Miniweb"
if [[ -x "${VENV_PY}" ]]; then
  if "${VENV_PY}" -c "import uvicorn" >/dev/null 2>&1; then
    ok "uvicorn disponible en venv"
  else
    warn "uvicorn no está instalado en venv"
  fi
else
  warn "Entorno virtual no encontrado"
fi

if command -v piper >/dev/null 2>&1; then
  ok "piper en $(command -v piper)"
else
  warn "piper no está en PATH"
fi

log "Modelos Piper"
if [[ -d "${MODELS_DIR}" ]]; then
  if [[ -f "${MODELS_DIR}/.default-voice" ]]; then
    def_voice=$(<"${MODELS_DIR}/.default-voice")
    if [[ -n "${def_voice}" && -s "${MODELS_DIR}/${def_voice}.onnx" && -s "${MODELS_DIR}/${def_voice}.onnx.json" ]]; then
      ok ".default-voice -> ${def_voice}"
    else
      warn ".default-voice apunta a voz inexistente (${def_voice})"
    fi
  else
    warn ".default-voice no existe"
  fi
  pair_found=false
  shopt -s nullglob
  for model in "${MODELS_DIR}"/*.onnx; do
    base="${model%.onnx}"
    if [[ -s "${base}.onnx" && -s "${base}.onnx.json" ]]; then
      ok "Modelo $(basename "${base}") listo"
      pair_found=true
    fi
  done
  shopt -u nullglob
  if [[ "${pair_found}" == false ]]; then
    warn "No se encontraron pares onnx/json"
  fi
else
  warn "${MODELS_DIR} no existe"
fi

log "Propietarios de venv y caché pip"
if [[ -d "${APP_DIR}/.venv" ]]; then
  owner=$(stat -c '%U' "${APP_DIR}/.venv" 2>/dev/null || echo "?")
  printf '[ok] owner .venv=%s\n' "${owner}"
fi
if [[ -d "${PIP_CACHE}" ]]; then
  owner=$(stat -c '%U' "${PIP_CACHE}" 2>/dev/null || echo "?")
  printf '[ok] owner pip-cache=%s\n' "${owner}"
else
  warn "${PIP_CACHE} no existe"
fi

ASSETS="${APP_DIR}/bascula/ui/assets/mascota/_gen"
if ls "${ASSETS}"/*.png >/dev/null 2>&1; then
  echo "[ok] Mascota PNG generados en ${ASSETS}"
else
  echo "[warn] No hay PNG generados de la mascota; intenta: bash scripts/build-mascot-assets.sh"
fi

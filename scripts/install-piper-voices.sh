#!/usr/bin/env bash
set -euo pipefail

VOICE="${1:-es_ES-sharvard-medium}"
MODELS_DIR="/opt/piper/models"
BASE_URL="https://github.com/DanielGTdiabetes/bascula-cam/releases/download/voices-v1"

log() { printf '[inst] %s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*"; }
err() { printf '[err] %s\n' "$*" >&2; }

download_voice() {
  local file="$1"
  local dest="${MODELS_DIR}/${file}"
  if [[ -f "${dest}" ]]; then
    log "${file} ya presente"
    return 0
  fi
  local url="${BASE_URL}/${file}"
  log "Descargando ${file}"
  if ! curl -fSL --retry 3 --retry-delay 2 -o "${dest}.tmp" "${url}"; then
    rm -f "${dest}.tmp"
    err "No se pudo descargar ${url}"
    return 1
  fi
  if [[ ! -s "${dest}.tmp" ]]; then
    rm -f "${dest}.tmp"
    err "Descarga vacía de ${url}"
    return 1
  fi
  mv "${dest}.tmp" "${dest}"
  chmod 0644 "${dest}"
  return 0
}

install -d -m 0755 "${MODELS_DIR}"

download_voice "${VOICE}.onnx" || warn "Fallo al obtener ${VOICE}.onnx"
download_voice "${VOICE}.onnx.json" || warn "Fallo al obtener ${VOICE}.onnx.json"

if command -v piper >/dev/null 2>&1; then
  printf '%s\n' "${VOICE}" > "${MODELS_DIR}/.default-voice"
  chmod 0644 "${MODELS_DIR}/.default-voice"
  log "Modelo por defecto configurado en ${VOICE}"
else
  warn "piper no está disponible; se instaló solo el modelo"
fi

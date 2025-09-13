#!/usr/bin/env bash
set -euo pipefail
#
# install-ai-extras.sh — Instala componentes pesados de IA (Whisper, TFLite, etc.)
#

log()  { printf "\033[1;34m[ai-xtra]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }
err()  { printf "\033[1;31m[ERR ]\033[0m %s\n" "$*"; }

require_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    err "Ejecuta con sudo: sudo ./install-ai-extras.sh"
    exit 1
  fi
}
require_root

BASCULA_ROOT="/opt/bascula"
BASCULA_CURRENT_LINK="${BASCULA_ROOT}/current"

if [[ ! -d "${BASCULA_CURRENT_LINK}" ]]; then
  err "No se encontró la instalación principal en ${BASCULA_CURRENT_LINK}."
  err "Por favor, ejecuta 'install-core.sh' primero."
  exit 1
fi

VENV_PY="${BASCULA_CURRENT_LINK}/.venv/bin/python"
TARGET_USER="$(stat -c '%U' ${BASCULA_CURRENT_LINK})"
TARGET_GROUP="$(stat -c '%G' ${BASCULA_CURRENT_LINK})"

# --- 1. IA: Vision-lite (TFLite) ---
log "Instalando TFLite Runtime..."
"${VENV_PY}" -m pip install "tflite-runtime>=2.14"
log "TFLite instalado."

# --- 2. IA: ASR (whisper.cpp) ---
log "Instalando Whisper.cpp para reconocimiento de voz (puede tardar)..."
if git clone https://github.com/ggerganov/whisper.cpp /opt/whisper.cpp; then
  (
    cd /opt/whisper.cpp
    make -j"$(nproc)" || warn "La compilación de whisper.cpp falló."
    if [[ ! -f models/ggml-tiny-es.bin ]]; then
      # El script original para descargar ha cambiado, usamos curl directo
      curl -L -o models/ggml-tiny-es.bin https://ggml.ggerganov.com/whisper/ggml-tiny-es.bin || warn "La descarga del modelo de Whisper falló."
    fi
  )
  chown -R "${TARGET_USER}:${TARGET_GROUP}" /opt/whisper.cpp
  log "Whisper.cpp instalado."
else
  warn "No se pudo clonar el repositorio de whisper.cpp."
fi

# --- 3. IA: OCR robusto (PaddleOCR) ---
log "Instalando motor de OCR avanzado (PaddleOCR)..."
log "Este paso puede tardar varios minutos."
# NOTA: La instalación de paddlepaddle puede ser compleja.
# Se recomienda usar la versión disponible en PiWheels.
"${VENV_PY}" -m pip install "paddlepaddle==2.6.1" paddleocr || warn "La instalación de PaddleOCR falló. El sistema usará Tesseract por defecto."

log "Instalación de extras de IA completada."

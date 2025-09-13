#!/usr/bin/env bash
set -euo pipefail
#
# install-ai-extras.sh (FIXED) — IA opcional para Bascula-Cam
# - TFLite Runtime desde piwheels si es posible
# - whisper.cpp compilado + modelo ES tiny
# - PaddleOCR opcional, con fallback si falla
#
log()  { printf "\033[1;34m[ai-xtra]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }
err()  { printf "\033[1;31m[ERR ]\033[0m %s\n" "$*"; }

require_root(){ if [[ ${EUID:-$(id -u)} -ne 0 ]]; then err "Ejecuta con sudo"; exit 1; fi; }
require_root

BASCULA_ROOT="/opt/bascula"
CUR_LINK="${BASCULA_ROOT}/current"
if [[ ! -d "${CUR_LINK}/.venv" ]]; then
  err "No se encontró venv en ${CUR_LINK}. Ejecuta primero install-core.sh"
  exit 1
fi
VENV_PY="${CUR_LINK}/.venv/bin/python"
VENV_PIP="${CUR_LINK}/.venv/bin/pip"
TARGET_USER="$(stat -c '%U' ${CUR_LINK})"
TARGET_GROUP="$(stat -c '%G' ${CUR_LINK})"

export PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
export PIP_INDEX_URL="${PIP_INDEX_URL:-https://www.piwheels.org/simple}"
export PIP_EXTRA_INDEX_URL="${PIP_EXTRA_INDEX_URL:-https://pypi.org/simple}"

# 1) TFLite Runtime
log "Instalando TFLite Runtime…"
if ! "${VENV_PY}" - <<'PY' >/dev/null 2>&1; then
    pass
PY
fi
# Intento por piwheels
if ! "${VENV_PIP}" install "tflite-runtime>=2.14"; then
  warn "tflite-runtime por piwheels falló. Probando wheel alternativo…"
  ARCH="$(uname -m)"
  WURL=""
  case "${ARCH}" in
    aarch64) WURL="https://github.com/kurokesu/raspberry-pi-tensorflow-wheel/releases/download/v2.14.0/tflite_runtime-2.14.0-cp311-cp311-linux_aarch64.whl" ;;
    armv7l)  WURL="https://github.com/kurokesu/raspberry-pi-tensorflow-wheel/releases/download/v2.14.0/tflite_runtime-2.14.0-cp311-cp311-linux_armv7l.whl" ;;
  esac
  if [[ -n "${WURL}" ]]; then
    TMPW="$(mktemp)"; if curl -fL --retry 2 -m 60 -o "${TMPW}" "${WURL}"; then
      "${VENV_PIP}" install "${TMPW}" || warn "No se pudo instalar tflite-runtime"
    fi; rm -f "${TMPW}" || true
  fi
fi

# 2) whisper.cpp
log "Instalando whisper.cpp…"
if [[ ! -d /opt/whisper.cpp/.git ]]; then
  if git clone https://github.com/ggerganov/whisper.cpp /opt/whisper.cpp; then
    ( cd /opt/whisper.cpp && make -j"$(nproc)" ) || warn "Compilación whisper.cpp falló"
    install -d -m 0755 /opt/whisper.cpp/models
    curl -fL -o /opt/whisper.cpp/models/ggml-tiny-es.bin https://ggml.ggerganov.com/whisper/ggml-tiny-es.bin || true
    chown -R "${TARGET_USER}:${TARGET_GROUP}" /opt/whisper.cpp
  else
    warn "No se pudo clonar whisper.cpp"
  fi
else
  log "whisper.cpp ya existe. Omitiendo."
fi

# 3) PaddleOCR (opcional)
if [[ "${INSTALL_PADDLEOCR:-0}" = "1" ]]; then
  log "Instalando PaddleOCR (opcional)…"
  if ! "${VENV_PIP}" install "paddlepaddle==2.6.1" paddleocr; then
    warn "PaddleOCR falló; usarás Tesseract por defecto."
  fi
else
  log "Omitiendo PaddleOCR (estable por defecto con Tesseract)."
fi

log "Extras de IA instalados."

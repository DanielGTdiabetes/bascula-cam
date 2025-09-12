#!/usr/bin/env bash
set -euo pipefail
# scripts/build-offline-bundle.sh
# Crea un paquete offline compatible con /boot/bascula-offline
# Uso:
#   ./scripts/build-offline-bundle.sh <dest_dir> [VOICE1 VOICE2 ...]
# Env:
#   WITH_PADDLE=1   # incluir wheels de paddlepaddle y paddleocr (si disponibles)
#   PYTHON=python3  # intérprete para pip download

if [[ $# -lt 1 ]]; then
  echo "Uso: $0 <dest_dir> [VOICE1 VOICE2 ...]" >&2
  exit 1
fi

DEST_DIR="$1"; shift || true
if [[ $# -ge 1 ]]; then
  VOICES=("$@")
else
  VOICES=("es_ES-mls-medium" "es_ES-mls-low")
fi

mkdir -p "${DEST_DIR}/wheels" "${DEST_DIR}/piper-voices" "${DEST_DIR}/piper/bin" "${DEST_DIR}/whisper"

PY=${PYTHON:-python3}
echo "[offline] Descargando wheels básicas a ${DEST_DIR}/wheels"
"${PY}" -m pip download -d "${DEST_DIR}/wheels" \
  --only-binary=:all: --prefer-binary \
  --index-url "${PIP_INDEX_URL:-https://www.piwheels.org/simple}" \
  --extra-index-url "${PIP_EXTRA_INDEX_URL:-https://pypi.org/simple}" \
  pyserial pillow fastapi "uvicorn[standard]" pytesseract requests pyzbar "pytz>=2024.1" \
  tflite-runtime==2.14.0 opencv-python-headless numpy piper-tts rapidocr-onnxruntime || true

if [[ "${WITH_PADDLE:-0}" = "1" ]]; then
  echo "[offline] Incluyendo wheels opcionales: paddlepaddle + paddleocr (si disponibles)"
  "${PY}" -m pip download -d "${DEST_DIR}/wheels" \
    --only-binary=:all: --prefer-binary \
    --index-url "${PIP_INDEX_URL:-https://www.piwheels.org/simple}" \
    --extra-index-url "${PIP_EXTRA_INDEX_URL:-https://pypi.org/simple}" \
    paddlepaddle==2.6.2 paddleocr==2.7.0.3 || true
fi

for VOICE in "${VOICES[@]}"; do
  echo "[offline] Descargando voz Piper: ${VOICE}"
  curl -fL -o "${DEST_DIR}/piper-voices/${VOICE}.tar.gz" \
    "https://github.com/rhasspy/piper/releases/download/v1.2.0/${VOICE}.tar.gz" || true
done

ARCH="$(uname -m || echo unknown)"
PIPER_BIN_URL=""
case "${ARCH}" in
  aarch64) PIPER_BIN_URL="https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_aarch64.tar.gz" ;;
  armv7l)  PIPER_BIN_URL="https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_armv7l.tar.gz" ;;
  x86_64)  PIPER_BIN_URL="https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz" ;;
esac
if [[ -n "${PIPER_BIN_URL}" ]]; then
  TMP_TGZ="$(mktemp -t piper_bin_XXXXXX).tgz"
  echo "[offline] Descargando binario Piper (${ARCH})"
  if curl -fL -o "${TMP_TGZ}" "${PIPER_BIN_URL}" && tar -tzf "${TMP_TGZ}" >/dev/null 2>&1; then
    tar -xzf "${TMP_TGZ}" -C "${DEST_DIR}/piper/bin" --strip-components=1 || true
  fi
  rm -f "${TMP_TGZ}" || true
  # Normalizar ruta del ejecutable si quedó anidado
  F_BIN="$(find "${DEST_DIR}/piper/bin" -type f -name piper 2>/dev/null | head -n1 || true)"
  if [[ -n "${F_BIN}" ]]; then chmod +x "${F_BIN}"; fi
fi

echo "[offline] Descargando modelo Whisper tiny-es"
curl -fL -o "${DEST_DIR}/whisper/ggml-tiny-es.bin" \
  "https://ggml.ggerganov.com/whisper/ggml-tiny-es.bin" || true

echo "[offline] Paquete listo en: ${DEST_DIR}"
echo "Copia esta carpeta a la partición BOOT como /boot/bascula-offline"

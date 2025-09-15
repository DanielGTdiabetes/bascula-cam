#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

VOICES_BASE="https://github.com/DanielGTdiabetes/bascula-cam/releases/download/voices-v1"
PIPER_MODELS_DIR="/opt/piper/models"

PIPER_VOICE="${PIPER_VOICE:-es_ES-sharvard-medium}"
case "${PIPER_VOICE}" in
  es_ES-sharvard-medium|es_ES-davefx-medium|es_ES-carlfm-x_low)
    ;;
  *)
    echo "[err] Voz '${PIPER_VOICE}' no soportada. Usa: es_ES-sharvard-medium | es_ES-davefx-medium | es_ES-carlfm-x_low" >&2
    exit 1
    ;;
esac

install -d -m 0755 "${PIPER_MODELS_DIR}"

TMP_WORK=""
cleanup_tmp() {
  if [[ -n "${TMP_WORK}" && -d "${TMP_WORK}" ]]; then
    rm -rf "${TMP_WORK}"
  fi
  TMP_WORK=""
}
trap cleanup_tmp EXIT

install_piper_bin() {
  if command -v piper >/dev/null 2>&1; then
    return 0
  fi

  local arch="$(uname -m)"
  local url=""
  case "${arch}" in
    aarch64)
      url="https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_aarch64.tar.gz"
      ;;
    armv7l|armv7hf|armv8l|armv6l|armv6)
      url="https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_armv7l.tar.gz"
      ;;
    x86_64)
      url="https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz"
      ;;
    *)
      echo "[err] Arquitectura no soportada para Piper: ${arch}" >&2
      exit 1
      ;;
  esac

  TMP_WORK="$(mktemp -d)"
  curl -fSL -o "${TMP_WORK}/piper.tgz" "${url}"
  tar -xzf "${TMP_WORK}/piper.tgz" -C "${TMP_WORK}"
  local PIPER_BIN
  PIPER_BIN="$(find "${TMP_WORK}" -type f -name piper -perm -111 | head -n1 || true)"
  test -n "${PIPER_BIN}" || { echo "[err] No se encontró ejecutable piper"; exit 1; }
  install -m 0755 "${PIPER_BIN}" /usr/local/bin/piper
  rm -rf "${TMP_WORK}"
  TMP_WORK=""
}

download_asset() {
  local asset="$1"
  local dest="${PIPER_MODELS_DIR}/${asset}"
  local url="${VOICES_BASE}/${asset}"
  local tmp="${dest}.tmp.$$"

  echo "[piper] Descargando ${asset} desde ${url}"
  if ! curl -fSL --retry 3 --retry-delay 2 -o "${tmp}" "${url}"; then
    rm -f "${tmp}"
    echo "[err] No pude descargar ${PIPER_VOICE} (${asset}) desde ${url}" >&2
    exit 1
  fi

  local size
  size="$(stat -c%s "${tmp}" 2>/dev/null || echo 0)"
  if [[ "${size}" -lt 1024 ]]; then
    rm -f "${tmp}"
    echo "[err] No pude descargar ${PIPER_VOICE} (${asset}) desde ${url}" >&2
    exit 1
  fi

  mv "${tmp}" "${dest}"
  chmod 0644 "${dest}"
}

install_piper_bin

download_asset "${PIPER_VOICE}.onnx"
download_asset "${PIPER_VOICE}.onnx.json"

echo "${PIPER_VOICE}" > "${PIPER_MODELS_DIR}/.default-voice"
echo "[ok] Voz ${PIPER_VOICE} instalada en /opt/piper/models"

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODELS_DIR="/opt/piper/models"
BASE_URL="https://github.com/DanielGTdiabetes/bascula-cam/releases/download/voices-v1"
ALT_BASE_URL="${ALT_BASE_URL:-}"
DEFAULT_VOICES=(
  "es_ES-sharvard-medium"
  "es_ES-davefx-medium"
  "es_ES-carlfm-x_low"
)

log() { printf '[inst] %s\n' "$*"; }
ok() { printf '[ok] %s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*"; }
err() { printf '[err] %s\n' "$*" >&2; }

if [[ $# -gt 0 ]]; then
  VOICES=()
  for voice in "$@"; do
    [[ -n "${voice}" ]] && VOICES+=("${voice}")
  done
  if [[ ${#VOICES[@]} -eq 0 ]]; then
    VOICES=("${DEFAULT_VOICES[@]}")
  fi
else
  VOICES=("${DEFAULT_VOICES[@]}")
fi

install -d -m 0755 "${MODELS_DIR}"

dry_curl() {
  curl -fL --retry 5 --retry-delay 2 --connect-timeout 10 --continue-at - "$@"
}

download_asset() {
  local asset="$1"
  local min_size="$2"
  local dest="${MODELS_DIR}/${asset}"
  local tmp="${dest}.tmp"

  if [[ -s "${dest}" ]]; then
    ok "${asset} ya existe"
    return 0
  fi

  rm -f "${tmp}"
  log "Descargando ${asset}"
  if ! dry_curl -o "${tmp}" "${BASE_URL}/${asset}"; then
    local status=$?
    rm -f "${tmp}" || true
    if [[ -n "${ALT_BASE_URL}" ]]; then
      warn "Descarga primaria falló (curl ${status}); intentando mirror"
      if ! dry_curl -o "${tmp}" "${ALT_BASE_URL}/${asset}"; then
        status=$?
        rm -f "${tmp}" || true
        err "No se pudo descargar ${asset} (curl ${status})"
        return 1
      fi
    else
      err "No se pudo descargar ${asset} (curl ${status})"
      return 1
    fi
  fi

  if [[ ! -s "${tmp}" ]]; then
    rm -f "${tmp}" || true
    err "Descarga vacía de ${asset}"
    return 1
  fi

  local size
  size=$(stat -c '%s' "${tmp}" 2>/dev/null || echo 0)
  if (( size < min_size )); then
    rm -f "${tmp}" || true
    err "${asset} tiene tamaño inesperado (${size} bytes)"
    return 1
  fi

  mv "${tmp}" "${dest}"
  chmod 0644 "${dest}"
  ok "Instalado ${asset}"
  return 0
}

voice_pairs_installed=0
default_candidate=""
for voice in "${VOICES[@]}"; do
  onnx_ok=0
  json_ok=0
  if download_asset "${voice}.onnx" 1048576; then
    onnx_ok=1
  fi
  if download_asset "${voice}.onnx.json" 1024; then
    json_ok=1
  fi
  if [[ ${onnx_ok} -eq 1 && ${json_ok} -eq 1 ]]; then
    if [[ -s "${MODELS_DIR}/${voice}.onnx" && -s "${MODELS_DIR}/${voice}.onnx.json" ]]; then
      ((voice_pairs_installed++))
      if [[ -z "${default_candidate}" ]]; then
        default_candidate="${voice}"
      fi
    fi
  fi
done

if (( voice_pairs_installed > 0 )); then
  if ! command -v piper >/dev/null 2>&1; then
    warn "piper no está en PATH"
  fi
  if [[ -n "${default_candidate}" ]]; then
    printf '%s\n' "${default_candidate}" > "${MODELS_DIR}/.default-voice"
    chmod 0644 "${MODELS_DIR}/.default-voice"
    ok "Voz por defecto: ${default_candidate}"
  fi
  exit 0
fi

err "No se instaló ninguna voz completa"
exit 1

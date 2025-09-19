#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODELS_DIR="/opt/piper/models"
VOICE_RELEASE_TAG="${VOICE_RELEASE_TAG:-voices-v1}"
ALT_BASE_URL="${ALT_BASE_URL:-}"
BASE_URLS=()

if [[ -n "${VOICE_RELEASE_TAG}" ]]; then
  BASE_URLS+=("https://github.com/DanielGTdiabetes/bascula-cam/releases/download/${VOICE_RELEASE_TAG}")
fi

# GitHub ofrece un alias para la última release publicada. Si el tag por defecto
# (voices-v1) cambia en el futuro, seguiremos teniendo un fallback válido.
BASE_URLS+=("https://github.com/DanielGTdiabetes/bascula-cam/releases/latest/download")

if [[ -n "${ALT_BASE_URL}" ]]; then
  BASE_URLS+=("${ALT_BASE_URL%/}")
fi
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

download_from_huggingface() {
  local voice="$1"
  local ext="$2"
  local min_size="$3"
  local tmp="$4"

  local locale="${voice%%-*}"
  local rest="${voice#*-}"
  local quality="${rest##*-}"
  local corpus="${rest%-${quality}}"
  local language="${locale%%_*}"

  if [[ -z "${language}" || -z "${corpus}" || -z "${quality}" ]]; then
    return 1
  fi

  local base="https://huggingface.co/rhasspy/piper-voices/resolve/main"
  local url="${base}/${language}/${locale}/${corpus}/${quality}/${voice}.${ext}"

  warn "Intentando Hugging Face: ${url}"
  if ! dry_curl -o "${tmp}" "${url}"; then
    rm -f "${tmp}" || true
    return 1
  fi

  local size
  size=$(stat -c '%s' "${tmp}" 2>/dev/null || echo 0)
  if (( size < min_size )); then
    rm -f "${tmp}" || true
    return 1
  fi

  return 0
}

download_asset() {
  local asset="$1"
  local min_size="$2"
  local dest="${MODELS_DIR}/${asset}"
  local tmp="${dest}.tmp"
  local voice="${asset%%.*}"
  local ext="${asset#${voice}.}"

  if [[ -s "${dest}" ]]; then
    ok "${asset} ya existe"
    return 0
  fi

  rm -f "${tmp}"
  log "Descargando ${asset}"

  local status=0
  local fetched=false

  for base in "${BASE_URLS[@]}"; do
    [[ -z "${base}" ]] && continue
    if dry_curl -o "${tmp}" "${base}/${asset}"; then
      fetched=true
      break
    else
      status=$?
      rm -f "${tmp}" || true
      warn "Descarga falló desde ${base}/${asset} (curl ${status})"
    fi
  done

  if [[ "${fetched}" != true ]]; then
    if download_from_huggingface "${voice}" "${ext}" "${min_size}" "${tmp}"; then
      fetched=true
    else
      err "No se pudo descargar ${asset}"
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

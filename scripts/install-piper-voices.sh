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

# Determinar las voces a instalar y mantener compatibilidad con VOICE
VOICE="${DEFAULT_VOICES[0]}"
if [[ $# -eq 0 ]]; then
  VOICES=("${DEFAULT_VOICES[@]}")
elif [[ $# -eq 1 ]]; then
  VOICE="$1"
  VOICES=("$1")
else
  VOICE="$1"
  VOICES=("$@")
fi

# Si no se construyó el array (caso 0 y 1 argumentos ya gestionados)
if [[ ${#VOICES[@]} -eq 0 ]]; then
  VOICES=("${DEFAULT_VOICES[@]}")
fi

install -d -m 0755 "${MODELS_DIR}"

try_download() {
  local url="$1"
  local dest_tmp="$2"
  if curl -fSL --retry 5 --retry-delay 2 --connect-timeout 10 --continue-at - -o "${dest_tmp}" "${url}"; then
    return 0
  fi
  return $?
}

download_asset() {
  local asset="$1"
  local min_size="$2"
  local dest="${MODELS_DIR}/${asset}"
  local tmp="${dest}.tmp"

  if [[ -s "${dest}" ]]; then
    ok "${asset} ya presente"
    return 0
  fi

  rm -f "${tmp}"
  log "Descargando ${asset}"

  local primary_url="${BASE_URL}/${asset}"
  if ! try_download "${primary_url}" "${tmp}"; then
    local status=$?
    rm -f "${tmp}"
    if [[ ${status} -eq 22 ]]; then
      if [[ -n "${ALT_BASE_URL}" ]]; then
        log "Descargando ${asset} desde mirror"
        if ! try_download "${ALT_BASE_URL}/${asset}" "${tmp}"; then
          status=$?
          rm -f "${tmp}"
          err "Fallo en descarga desde mirror (${status}) para ${asset}"
          return 1
        fi
      else
        warn "Mirror no configurado"
        err "No se pudo descargar ${asset} desde ${primary_url}"
        return 1
      fi
    else
      err "No se pudo descargar ${asset} desde ${primary_url} (curl ${status})"
      return 1
    fi
  fi

  if [[ ! -s "${tmp}" ]]; then
    rm -f "${tmp}"
    err "Descarga vacía de ${asset}"
    return 1
  fi

  local size
  size=$(stat -c '%s' "${tmp}")
  if (( size < min_size )); then
    rm -f "${tmp}"
    err "${asset} con tamaño inesperado (${size} bytes)"
    return 1
  fi

  mv "${tmp}" "${dest}"
  chmod 0644 "${dest}"

  if [[ -f "${SCRIPT_DIR}/voices.sha256" ]]; then
    local sha_tmp
    sha_tmp="$(mktemp)"
    if ! (cd "${MODELS_DIR}" && sha256sum -c --ignore-missing "${SCRIPT_DIR}/voices.sha256" >"${sha_tmp}" 2>&1); then
      cat "${sha_tmp}" >&2 || true
      rm -f "${dest}" "${sha_tmp}" || true
      err "Fallo en verificación sha256 para ${asset}"
      return 1
    fi
    rm -f "${sha_tmp}" || true
  fi

  ok "Instalado ${asset}"
  return 0
}

voice_pairs_installed=0
for voice in "${VOICES[@]}"; do
  voice_ok=true
  if ! download_asset "${voice}.onnx" 1048576; then
    voice_ok=false
  fi
  if ! download_asset "${voice}.onnx.json" 1024; then
    voice_ok=false
  fi
  if ${voice_ok}; then
    ((voice_pairs_installed++))
  fi
done

if command -v piper >/dev/null 2>&1; then
  if [[ ${#VOICES[@]} -gt 0 ]]; then
    printf '%s\n' "${VOICES[0]}" > "${MODELS_DIR}/.default-voice"
    chmod 0644 "${MODELS_DIR}/.default-voice"
    ok "Voz por defecto establecida en ${VOICES[0]}"
  fi
else
  warn "piper no está disponible; se omite .default-voice"
fi

if (( voice_pairs_installed > 0 )); then
  exit 0
fi

err "No se pudo instalar ninguna voz"
exit 1

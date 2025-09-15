#!/usr/bin/env bash
set -euo pipefail

# Instala Piper y una voz española.
# Variables:
#   PIPER_VOICE  -> voz a instalar (defecto: es_ES-sharvard-medium)
#   VOICES_BASE  -> URL base de Release con modelos (opcional)

log(){ printf '\033[1;34m[inst]\033[0m %s\n' "$*"; }
warn(){ printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
err(){ printf '\033[1;31m[err ]\033[0m %s\n' "$*"; }

PIPER_VOICE="${PIPER_VOICE:-es_ES-sharvard-medium}"
VOICES_BASE="${VOICES_BASE:-https://github.com/bascula-cam/voices/releases/download/latest}"
DEST="/opt/piper/models"
install -d -m 0755 "$DEST"

# --- Piper binary ---
if ! command -v piper >/dev/null 2>&1; then
  arch="$(uname -m)"
  case "$arch" in
    aarch64) BIN="piper_linux_aarch64";;
    armv7l|armv8l|armv6l) BIN="piper_linux_armv7";;
    x86_64) BIN="piper_linux_x86_64";;
    *) err "Arquitectura no soportada: $arch"; exit 1;;
  esac
  tmp="$(mktemp -d)"
  curl -fsSL "https://github.com/rhasspy/piper/releases/latest/download/${BIN}.tar.gz" | tar -xz -C "$tmp"
  install -m 0755 "$tmp/piper" /usr/local/bin/piper
  rm -rf "$tmp"
  log "Piper instalado en /usr/local/bin"
else
  log "Piper ya está instalado"
fi

VOICE_ONNX="${DEST}/${PIPER_VOICE}.onnx"
VOICE_JSON="${DEST}/${PIPER_VOICE}.onnx.json"

get_from_base(){
  local base="$1"
  curl -fsSL --retry 3 -o "$VOICE_ONNX" "${base}/${PIPER_VOICE}.onnx" || return 1
  curl -fsSL --retry 3 -o "$VOICE_JSON" "${base}/${PIPER_VOICE}.onnx.json" || return 1
}

if get_from_base "$VOICES_BASE"; then
  log "Voz ${PIPER_VOICE} descargada desde Release"
else
  warn "Voz no encontrada en Release; usando HuggingFace"
  locale="${PIPER_VOICE%%-*}"
  rest="${PIPER_VOICE#*-}"
  quality="${rest##*-}"
  corpus="${rest%-${quality}}"
  HF_BASE="https://huggingface.co/rhasspy/piper-voices/resolve/main/es/${locale}/${corpus}/${quality}"
  if get_from_base "$HF_BASE"; then
    log "Voz ${PIPER_VOICE} descargada desde HuggingFace"
  else
    err "No pude descargar la voz ${PIPER_VOICE}"; exit 1
  fi
fi

echo "$PIPER_VOICE" > "${DEST}/.default-voice"
log "Voz por defecto: ${PIPER_VOICE}"
log "Listo. Modelos en ${DEST}"

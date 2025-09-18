#!/usr/bin/env bash
set -euo pipefail

MODELS_DIR="/opt/piper/models"
STATUS=0

log() { printf '[piper] %s\n' "$*"; }
warn() { printf '[piper][WARN] %s\n' "$*"; }
err() { printf '[piper][ERR] %s\n' "$*" >&2; STATUS=1; }

if [[ ! -d "$MODELS_DIR" ]]; then
  warn "$MODELS_DIR no existe; voz no instalada"
  exit 0
fi

VOICE_FILE="$MODELS_DIR/.default-voice"
VOICE=""
if [[ -f "$VOICE_FILE" ]]; then
  VOICE="$(<"$VOICE_FILE")"
  VOICE="${VOICE##*/}"
  VOICE="${VOICE%.onnx}"
  if [[ -n "$VOICE" ]]; then
    log "Voz por defecto: $VOICE"
  else
    warn '.default-voice vacío'
  fi
else
  warn 'Archivo .default-voice ausente'
fi

if [[ -n "$VOICE" && -f "$MODELS_DIR/${VOICE}.onnx" ]]; then
  log "Modelo ${VOICE}.onnx presente"
else
  warn "Modelo por defecto no encontrado"
fi

if [[ -n "$VOICE" && -f "$MODELS_DIR/${VOICE}.onnx.json" ]]; then
  log "Metadata ${VOICE}.onnx.json presente"
fi

if ! command -v piper >/dev/null 2>&1; then
  warn 'Binario piper no encontrado en PATH'
  exit 0
fi

tmp_output="$(mktemp)"
trap 'rm -f "$tmp_output"' EXIT

if [[ -n "$VOICE" && -f "$MODELS_DIR/${VOICE}.onnx" ]]; then
  if echo '{"text":"prueba"}' | piper --model "$MODELS_DIR/${VOICE}.onnx" --output-raw "$tmp_output" >/dev/null 2>&1; then
    log 'Síntesis mínima OK'
  else
    warn "Falló síntesis con la voz ${VOICE}"
  fi
else
  warn 'No se puede sintetizar: voz por defecto ausente'
fi

exit "$STATUS"

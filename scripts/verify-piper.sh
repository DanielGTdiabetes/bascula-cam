#!/usr/bin/env bash
set -euo pipefail

MODELS="/opt/piper/models"
if [[ ! -d "$MODELS" ]]; then
  echo "[piper][warn] Directorio $MODELS no encontrado; saltando comprobación"
  exit 0
fi

VOICE_FILE="$MODELS/.default-voice"
VOICE=""
if [[ -f "$VOICE_FILE" ]]; then
  VOICE="$(<"$VOICE_FILE")"
  VOICE="${VOICE##*/}"
  VOICE="${VOICE%.onnx}"
  echo "[piper] Voz por defecto: ${VOICE:-<no definida>}"
else
  echo "[piper][warn] Archivo .default-voice ausente"
fi

if [[ -n "$VOICE" && -f "$MODELS/${VOICE}.onnx" ]]; then
  echo "[piper] Modelo ${VOICE}.onnx presente"
else
  echo "[piper][warn] Modelo por defecto no descargado"
fi

if ! command -v piper >/dev/null 2>&1; then
  echo "[piper][warn] Binario piper no encontrado en PATH"
  exit 0
fi

if [[ -n "$VOICE" && -f "$MODELS/${VOICE}.onnx" ]]; then
  if ! echo '{"text":"Prueba de voz"}' | piper --model "$MODELS/${VOICE}.onnx" --output-raw >/dev/null 2>&1; then
    echo "[piper][warn] Falló síntesis con la voz ${VOICE}"
  else
    echo "[piper] Síntesis mínima OK"
  fi
else
  echo "[piper][warn] Saltando síntesis: voz no definida"
fi

exit 0

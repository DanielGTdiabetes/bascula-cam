#!/usr/bin/env bash
set -euo pipefail

# scripts/sound-selftest.sh — Prueba básica de audio
# - Requiere sox, aplay, espeak-ng y opcionalmente piper
# - No necesita privilegios de root

if [[ $(id -u) -eq 0 ]]; then
  echo "[ERR ] No ejecutar como root" >&2
  exit 1
fi

echo "=== Dispositivos ALSA disponibles ==="
aplay -l || true

PLAY_ARGS=()
if [[ -n "${BASCULA_APLAY_DEVICE:-}" ]]; then
  PLAY_ARGS=(-D "$BASCULA_APLAY_DEVICE")
fi

tmp_beep=$(mktemp --suffix=.wav)
sox -n -r 44100 -c 1 "$tmp_beep" synth 0.2 sine 1000 >/dev/null 2>&1
echo "[info] Reproduciendo beep"
aplay -q "${PLAY_ARGS[@]}" "$tmp_beep" || echo "[warn] aplay falló con beep"
rm -f "$tmp_beep"

echo "[info] Probando espeak-ng"
espeak-ng -v es "Prueba de voz de la báscula." --stdout | aplay -q "${PLAY_ARGS[@]}" || echo "[warn] espeak-ng o aplay falló"

if command -v piper >/dev/null 2>&1 && [[ -f /opt/piper/models/es_ES-sharvard-medium.onnx ]]; then
  tmp_wav=$(mktemp --suffix=.wav)
  echo "[info] Probando Piper (es_ES-sharvard-medium)"
  piper --model /opt/piper/models/es_ES-sharvard-medium.onnx \
        --output_file "$tmp_wav" --sentence "Prueba de voz de Piper." >/dev/null 2>&1 || {
    echo "[warn] Piper falló"; rm -f "$tmp_wav"; exit 1; }
  aplay -q "${PLAY_ARGS[@]}" "$tmp_wav" || echo "[warn] aplay falló con Piper"
  rm -f "$tmp_wav"
else
  echo "[warn] Piper o modelo no disponibles; omito prueba"
fi

echo "[ok] Prueba de audio finalizada"


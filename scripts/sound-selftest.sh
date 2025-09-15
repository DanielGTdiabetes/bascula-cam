#!/usr/bin/env bash
set -euo pipefail

log(){ echo "[$1] ${2:-}"; }
die(){ log ERR "${1}"; exit 1; }

if [[ ${EUID:-$(id -u)} -eq 0 ]]; then
  die "No ejecutar este script como root"
fi

log INFO "=== Dispositivos ALSA disponibles ==="
aplay -l || log WARN "aplay -l falló"

PLAY_ARGS=()
if [[ -n "${BASCULA_APLAY_DEVICE:-}" ]]; then
  PLAY_ARGS=(-D "${BASCULA_APLAY_DEVICE}")
  log INFO "Usando dispositivo ALSA ${BASCULA_APLAY_DEVICE}"
fi

BEEP_FILE="$(mktemp --suffix=.wav)"
PIPER_FILE=""
cleanup(){
  rm -f "${BEEP_FILE}" "${PIPER_FILE}" 2>/dev/null || true
}
trap cleanup EXIT

log INFO "Generando beep con SoX"
sox -n -r 44100 -c 1 "${BEEP_FILE}" synth 0.3 sine 1000 >/dev/null 2>&1
log INFO "Reproduciendo beep"
aplay -q "${PLAY_ARGS[@]}" "${BEEP_FILE}" || log WARN "aplay falló durante el beep"

log INFO "Probando espeak-ng"
if ! espeak-ng -v es "Prueba breve de voz." --stdout | aplay -q "${PLAY_ARGS[@]}"; then
  log WARN "espeak-ng o aplay falló"
fi

VOICE_CANDIDATE="${PIPER_VOICE:-es_ES-sharvard-medium}"
if [[ ! -f "/opt/piper/models/${VOICE_CANDIDATE}.onnx" ]]; then
  for candidate in es_ES-sharvard-medium es_ES-davefx-medium es_ES-carlfm-x_low; do
    if [[ -f "/opt/piper/models/${candidate}.onnx" ]]; then
      VOICE_CANDIDATE="${candidate}"
      break
    fi
  done
fi

if command -v piper >/dev/null 2>&1 && [[ -f "/opt/piper/models/${VOICE_CANDIDATE}.onnx" ]]; then
  PIPER_FILE="$(mktemp --suffix=.wav)"
  log INFO "Probando Piper con voz ${VOICE_CANDIDATE}"
  if piper --model "/opt/piper/models/${VOICE_CANDIDATE}.onnx" --output_file "${PIPER_FILE}" --sentence "Prueba rápida de síntesis con Piper." >/dev/null 2>&1; then
    aplay -q "${PLAY_ARGS[@]}" "${PIPER_FILE}" || log WARN "aplay falló al reproducir Piper"
  else
    log WARN "Piper falló al sintetizar"
  fi
else
  log WARN "Piper o el modelo ${VOICE_CANDIDATE} no están disponibles"
fi

log INFO "Prueba de audio finalizada"

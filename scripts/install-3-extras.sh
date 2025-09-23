#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log()  { printf "\033[1;34m[extras]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn ]\033[0m %s\n" "$*"; }
err()  { printf "\033[1;31m[err  ]\033[0m %s\n" "$*"; }

usage() {
  cat <<USAGE
Uso: ${0##*/} [--with-piper] [--piper-voice VOZ]

Instala componentes opcionales de Báscula.

Opciones:
  --with-piper         Instala Piper TTS y una voz en español.
  --piper-voice VOZ    Selecciona la voz (por defecto: es_ES-mls-medium).
  -h, --help           Muestra esta ayuda.
USAGE
}

WITH_PIPER=0
PIPER_VOICE="es_ES-mls-medium"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-piper)
      WITH_PIPER=1
      shift
      ;;
    --piper-voice)
      if [[ $# -lt 2 ]]; then
        err "--piper-voice requiere un argumento"
        usage
        exit 1
      fi
      PIPER_VOICE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      err "Opción desconocida: $1"
      usage
      exit 1
      ;;
  esac
done

if (( WITH_PIPER )); then
  log "Instalando Piper TTS (voz ${PIPER_VOICE})"
  DEFAULT_VOICE="${PIPER_VOICE}" bash "${SCRIPT_DIR}/install-piper-voices.sh"

  if ! command -v piper >/dev/null 2>&1; then
    err "Piper no está disponible tras la instalación"
    exit 1
  fi

  if ! piper --list-voices >/tmp/piper_voices.txt 2>&1; then
    warn "piper --list-voices falló"
  else
    if ! grep -Fq "${PIPER_VOICE}" /tmp/piper_voices.txt; then
      warn "La voz ${PIPER_VOICE} no aparece en piper --list-voices"
    fi
  fi

  TEST_WAV="/tmp/piper_test.wav"
  MODEL="/usr/share/piper/voices/${PIPER_VOICE}.onnx"
  CONFIG="${MODEL}.json"
  if [[ -f "${MODEL}" && -f "${CONFIG}" ]]; then
    if ! printf 'Instalación correcta de Piper.' | piper --model "${MODEL}" --config "${CONFIG}" --output_file "${TEST_WAV}" >/dev/null 2>&1; then
      warn "No se pudo sintetizar audio de prueba con Piper"
    else
      log "Audio de prueba generado en ${TEST_WAV}"
    fi
  else
    warn "No se encontraron ficheros de voz (${MODEL})"
  fi
else
  log "Piper no se instalará (use --with-piper para habilitarlo)"
fi

log "Extras completados"

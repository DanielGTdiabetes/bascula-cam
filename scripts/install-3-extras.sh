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

WITH_PIPER="${WITH_PIPER:-0}"
PIPER_VOICE="${PIPER_VOICE:-es_ES-mls-medium}"

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
  sudo apt-get update -y
  sudo apt-get install -y piper piper-voices || true
  mkdir -p "$HOME/.config/bascula/voices"
  VOX="${PIPER_VOICE:-es_ES-mls-medium}"
  echo "default_voice=${VOX}" > "$HOME/.config/bascula/voices/config.ini"
  echo "Hola, esto es una prueba de Piper" | piper -m "/usr/share/piper-voices/${VOX}.onnx" -o /tmp/piper_test.wav || true
else
  log "Piper no se instalará (use --with-piper para habilitarlo)"
fi

log "Extras completados"

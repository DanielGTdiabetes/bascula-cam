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

if [[ "$WITH_PIPER" == "1" ]]; then
  log "Instalando Piper TTS (voz ${PIPER_VOICE})"
  sudo apt-get update -y
  sudo apt-get install -y piper piper-voices

  sudo install -d -m 0755 /opt/piper/voices
  voice_model="${PIPER_VOICE}.onnx"
  voice_config="${PIPER_VOICE}.onnx.json"
  src_dir="/usr/share/piper-voices"
  if [[ -f "${src_dir}/${voice_model}" ]]; then
    sudo install -m 0644 "${src_dir}/${voice_model}" "/opt/piper/voices/${voice_model}"
    if [[ -f "${src_dir}/${voice_config}" ]]; then
      sudo install -m 0644 "${src_dir}/${voice_config}" "/opt/piper/voices/${voice_config}"
    fi
  else
    warn "No se encontró el modelo ${voice_model} en ${src_dir}"
  fi

  mkdir -p "$HOME/.config/bascula/voices"
  echo "default_voice=${PIPER_VOICE}" > "$HOME/.config/bascula/voices/config.ini"

  if command -v piper >/dev/null 2>&1; then
    voices_log="/tmp/piper_voices.log"
    if piper --list-voices >"${voices_log}" 2>&1; then
      tail -n 5 "${voices_log}" || true
      rm -f "${voices_log}" 2>/dev/null || true
      echo "[OK] Piper"
    else
      warn "piper --list-voices falló; intentando síntesis de prueba"
      if [[ -f "/opt/piper/voices/${voice_model}" ]]; then
        if echo "Prueba de voz" | piper -m "/opt/piper/voices/${voice_model}" -f /tmp/piper_test.wav >/dev/null 2>&1; then
          echo "[OK] Piper"
        else
          warn "No se pudo ejecutar Piper"
        fi
      fi
    fi
  else
    warn "El comando piper no está disponible"
  fi
else
  log "Piper no se instalará (defina WITH_PIPER=1 para habilitarlo)"
fi

log "Extras completados"

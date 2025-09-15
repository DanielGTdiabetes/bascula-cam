#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

log(){ echo "[$1] ${2:-}"; }
die(){ log ERR "${1}"; exit 1; }

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  die "Este script debe ejecutarse con sudo o como root"
fi

TARGET_USER="${TARGET_USER:-${SUDO_USER:-pi}}"
if ! id "${TARGET_USER}" >/dev/null 2>&1; then
  die "El usuario objetivo '${TARGET_USER}' no existe"
fi
TARGET_GROUP="$(id -gn "${TARGET_USER}")"
TARGET_HOME="$(getent passwd "${TARGET_USER}" | cut -d: -f6)"
if [[ -z "${TARGET_HOME}" ]]; then
  die "No se pudo determinar el directorio home de ${TARGET_USER}"
fi

AUDIO_OPTION=""
for arg in "$@"; do
  case "$arg" in
    --audio=*) AUDIO_OPTION="${arg#*=}" ;;
  esac
done

run_as_target(){
  local quoted_cmd
  printf -v quoted_cmd ' %q' "$@"
  su - "${TARGET_USER}" -s /bin/bash -c "${quoted_cmd}"
}

log INFO "Instalando aplicación para ${TARGET_USER}"
install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_GROUP}" "${TARGET_HOME}/.config/bascula"

VENV_PATH="${REPO_ROOT}/.venv"
if [[ ! -d "${VENV_PATH}" ]]; then
  log INFO "Creando entorno virtual en ${VENV_PATH}"
  run_as_target python3 -m venv "${VENV_PATH}"
else
  log INFO "Entorno virtual ya existente en ${VENV_PATH}"
fi

log INFO "Actualizando pip/setuptools/wheel"
run_as_target "${VENV_PATH}/bin/pip" install --upgrade pip setuptools wheel
if [[ -f "${REPO_ROOT}/requirements.txt" ]]; then
  log INFO "Instalando dependencias desde requirements.txt"
  run_as_target "${VENV_PATH}/bin/pip" install -r "${REPO_ROOT}/requirements.txt"
else
  log WARN "No se encontró requirements.txt; omitiendo instalación"
fi

SERVICE_SRC="${REPO_ROOT}/systemd/bascula-ui.service"
SERVICE_DST="/etc/systemd/system/bascula-ui.service"
if [[ ! -f "${SERVICE_SRC}" ]]; then
  die "No se encontró ${SERVICE_SRC}"
fi
TMP_SERVICE="$(mktemp)"
cp "${SERVICE_SRC}" "${TMP_SERVICE}"
if [[ "${TARGET_USER}" != "pi" ]]; then
  sed -i "s/^User=.*/User=${TARGET_USER}/" "${TMP_SERVICE}"
fi
install -m 0644 "${TMP_SERVICE}" "${SERVICE_DST}"
rm -f "${TMP_SERVICE}"
systemctl daemon-reload

if systemctl list-unit-files | grep -q '^ocr-service.service'; then
  systemctl reset-failed ocr-service.service || true
fi
systemctl reset-failed bascula-ui.service 2>/dev/null || true

if [[ -n "${AUDIO_OPTION}" && "${AUDIO_OPTION,,}" == "max98357a" ]]; then
  log INFO "Configurando ALSA para MAX98357A"
  bash "${SCRIPT_DIR}/install-asound-default.sh" MAX98357A 0
fi

TMPDIR="$(mktemp -d)"
case "$(uname -m)" in
  aarch64) URL="https://github.com/rhasspy/piper/releases/latest/download/piper_arm64.tar.gz" ;;
  armv7l|arm) URL="https://github.com/rhasspy/piper/releases/latest/download/piper_armv7l.tar.gz" ;;
  x86_64) URL="https://github.com/rhasspy/piper/releases/latest/download/piper_linux_x86_64.tar.gz" ;;
  *) URL=""; log WARN "Arquitectura no soportada para Piper" ;;
esac
if [[ -n "${URL}" ]]; then
  log INFO "Descargando Piper desde ${URL}"
  curl -fSL -o "${TMPDIR}/piper.tgz" "${URL}"
  tar -xzf "${TMPDIR}/piper.tgz" -C "${TMPDIR}"
  PIPER_BIN="$(find "${TMPDIR}" -type f -name piper -perm -111 | head -n1 || true)"
  [[ -n "${PIPER_BIN}" ]] || die "No se encontró ejecutable 'piper' tras extraer"
  install -m 0755 "${PIPER_BIN}" /usr/local/bin/piper
  log INFO "Piper instalado en /usr/local/bin/piper"
fi
rm -rf "${TMPDIR}"

PIPER_VOICE="${PIPER_VOICE:-es_ES-sharvard-medium}"
case "${PIPER_VOICE}" in
  es_ES-sharvard-medium|es_ES-davefx-medium|es_ES-carlfm-x_low) ;;
  *) die "Voz Piper no soportada: ${PIPER_VOICE}" ;;
esac
VOICES_BASE="https://github.com/DanielGTdiabetes/bascula-cam/releases/download/voices-v1"
install -d -m 0755 /opt/piper/models

fetch_voice_file(){
  local url="$1" dest="$2" tmp size
  if [[ -f "${dest}" && $(stat -c%s "${dest}" 2>/dev/null || echo 0) -ge 1024 ]]; then
    log INFO "${dest} ya existe"
    return
  fi
  tmp="$(mktemp)"
  log INFO "Descargando ${url}"
  if ! curl -fSL --retry 3 --retry-delay 2 -o "${tmp}" "${url}"; then
    rm -f "${tmp}"
    die "Fallo al descargar ${url}"
  fi
  size=$(stat -c%s "${tmp}" 2>/dev/null || echo 0)
  if [[ "${size}" -lt 1024 ]]; then
    rm -f "${tmp}"
    die "Descarga corrupta (menos de 1KB) desde ${url}"
  fi
  install -m 0644 "${tmp}" "${dest}"
  rm -f "${tmp}"
}

fetch_voice_file "${VOICES_BASE}/${PIPER_VOICE}.onnx" "/opt/piper/models/${PIPER_VOICE}.onnx"
fetch_voice_file "${VOICES_BASE}/${PIPER_VOICE}.onnx.json" "/opt/piper/models/${PIPER_VOICE}.onnx.json"
log INFO "Voz ${PIPER_VOICE} instalada en /opt/piper/models"

systemctl enable --now x735-fan.service || true

set +e
log INFO "== Post-install checks =="
which piper || log WARN "piper no en PATH"
ls -lh /opt/piper/models || true
aplay -l || log WARN "aplay -l falló"

systemctl enable --now bascula-ui.service
sleep 2
if ! systemctl is-active --quiet bascula-ui.service; then
  log ERR "bascula-ui.service no está activo"
  journalctl -u bascula-ui -n 120 --no-pager || true
  exit 1
fi
log INFO "bascula-ui.service activo"
set -e

log INFO "Fase 2 completada"

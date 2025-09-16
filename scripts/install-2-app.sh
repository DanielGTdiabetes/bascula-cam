#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_USER="${TARGET_USER:-pi}"
TARGET_HOME="$(getent passwd "${TARGET_USER}" | cut -d: -f6)"
APP_DIR="${TARGET_HOME}/bascula-cam"
CFG_DIR="${TARGET_HOME}/.config/bascula"

log(){ echo "[$1] ${2:-}"; }
die(){ log ERR "${1}"; exit 1; }

usage(){
  cat <<'USAGE'
Uso: install-2-app.sh [--audio PERFIL]

  --audio PERFIL    Selecciona el perfil de audio (auto, max98357a, vc4hdmi, usb, none)
  -h, --help        Muestra esta ayuda
USAGE
  exit "${1:-0}"
}

AUDIO_PROFILE="auto"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --audio=*)
      AUDIO_PROFILE="${1#*=}"
      ;;
    --audio)
      shift || die "Falta valor para --audio"
      [[ $# -gt 0 ]] || die "Falta valor para --audio"
      AUDIO_PROFILE="$1"
      ;;
    -h|--help)
      usage 0
      ;;
    *)
      die "Opción no reconocida: $1"
      ;;
  esac
  shift || true
done
AUDIO_PROFILE="${AUDIO_PROFILE,,}"

AUDIO_DEVICE_PCM=""
AUDIO_CONTROL_CARD=""
AUDIO_PROFILE_DESC=""
AUDIO_PROFILE_RESOLVED="${AUDIO_PROFILE}"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  die "Este script debe ejecutarse con sudo o como root"
fi

if ! id "${TARGET_USER}" >/dev/null 2>&1; then
  die "El usuario objetivo '${TARGET_USER}' no existe"
fi
if [[ -z "${TARGET_HOME}" ]]; then
  die "No se pudo determinar el directorio home de ${TARGET_USER}"
fi

# Verificar si necesitamos instalar X11 para modo kiosko
install_minimal_x11_if_needed() {
  if ! command -v startx >/dev/null 2>&1; then
    log INFO "Raspberry Pi OS Lite detectado, instalando X11 mínimo para modo kiosko..."
    
    # Instalar X11 mínimo para modo kiosko
    apt-get update
    apt-get install -y \
      xserver-xorg-core \
      xserver-xorg-input-all \
      xserver-xorg-video-fbdev \
      xinit \
      x11-xserver-utils \
      unclutter \
      xterm
    
    log INFO "X11 mínimo instalado para modo kiosko"
  else
    log INFO "X11 ya está disponible"
  fi
}

install_minimal_x11_if_needed

install_if_different(){
  local src="$1" dest="$2" mode="$3"
  if [[ -f "${dest}" ]] && cmp -s "${src}" "${dest}"; then
    return 1
  fi
  install -m "${mode}" "${src}" "${dest}"
  return 0
}

detect_card_index(){
  local hint="${1:-}"
  command -v aplay >/dev/null 2>&1 || return 1
  local line idx id lower
  while IFS= read -r line; do
    if [[ "$line" =~ ^card[[:space:]]+([0-9]+):[[:space:]]*([^ ,]+) ]]; then
      idx="${BASH_REMATCH[1]}"
      id="${BASH_REMATCH[2]}"
      lower="$(printf '%s' "${id}" | tr '[:upper:]' '[:lower:]')"
      if [[ -z "${hint}" || "${lower}" == *"${hint}"* ]]; then
        printf '%s' "${idx}"
        return 0
      fi
    fi
  done < <(aplay -l 2>/dev/null || true)
  return 1
}

ensure_asound_conf(){
  local pcm_device="$1"
  local control_card="$2"
  local label="${3:-${pcm_device}}"
  local asound_conf="/etc/asound.conf"
  local tmp
  tmp="$(mktemp)"
  local ctl_card="${control_card}"
  if [[ -z "${ctl_card}" ]]; then
    ctl_card="0"
  fi
  if [[ ! "${ctl_card}" =~ ^[0-9]+$ ]]; then
    ctl_card="\"${ctl_card}\""
  fi
  cat <<ASOUND > "${tmp}"
pcm.!default {
    type plug
    slave.pcm "softvol"
}

pcm.softvol {
    type softvol
    slave {
        pcm "${pcm_device}"
    }
    control {
        name "SoftMaster"
        card ${ctl_card}
    }
    min_dB -51.0
    max_dB 0.0
}

ctl.!default {
    type hw
    card ${ctl_card}
}
ASOUND
  if install_if_different "${tmp}" "${asound_conf}" 0644; then
    log alsa "Configurado /etc/asound.conf para ${label}"
  else
    log alsa "/etc/asound.conf ya estaba configurado para ${label}"
  fi
  rm -f "${tmp}"
}

ensure_service_audio_dropin(){
  local device="$1"
  local label="${2:-${device}}"
  local dir="/etc/systemd/system/bascula-ui.service.d"
  local dropin="${dir}/10-audio.conf"
  if [[ -z "${device}" ]]; then
    if [[ -f "${dropin}" ]]; then
      rm -f "${dropin}"
      log alsa "Eliminado drop-in de audio para bascula-ui (sin perfil)"
    fi
    return
  fi
  install -d -m 0755 "${dir}"
  local tmp
  tmp="$(mktemp)"
  cat <<EOF > "${tmp}"
[Service]
Environment=BASCULA_APLAY_DEVICE=${device}
EOF
  if install_if_different "${tmp}" "${dropin}" 0644; then
    log alsa "Actualizado drop-in de audio (${label})"
  else
    log alsa "Drop-in de audio sin cambios (${label})"
  fi
  rm -f "${tmp}"
}

resolve_audio_profile(){
  local profile="$1"
  local idx=""
  AUDIO_PROFILE_RESOLVED="$profile"
  case "$profile" in
    auto|"")
      if idx=$(detect_card_index "hifiberry") || idx=$(detect_card_index "max98357") || idx=$(detect_card_index "i2s"); then
        AUDIO_PROFILE_RESOLVED="max98357a"
        AUDIO_DEVICE_PCM="plughw:${idx},0"
        AUDIO_CONTROL_CARD="${idx}"
        AUDIO_PROFILE_DESC="MAX98357A (tarjeta ${idx})"
      elif idx=$(detect_card_index "usb"); then
        AUDIO_PROFILE_RESOLVED="usb"
        AUDIO_DEVICE_PCM="plughw:${idx},0"
        AUDIO_CONTROL_CARD="${idx}"
        AUDIO_PROFILE_DESC="USB Audio (tarjeta ${idx})"
      elif idx=$(detect_card_index "vc4hdmi"); then
        AUDIO_PROFILE_RESOLVED="vc4hdmi"
        AUDIO_DEVICE_PCM="plughw:${idx},0"
        AUDIO_CONTROL_CARD="${idx}"
        AUDIO_PROFILE_DESC="VC4 HDMI (tarjeta ${idx})"
      else
        AUDIO_DEVICE_PCM="plughw:0,0"
        AUDIO_CONTROL_CARD="0"
        AUDIO_PROFILE_DESC="Dispositivo ALSA predeterminado (tarjeta 0)"
      fi
      ;;
    max98357a)
      if idx=$(detect_card_index "hifiberry") || idx=$(detect_card_index "max98357") || idx=$(detect_card_index "i2s"); then
        AUDIO_DEVICE_PCM="plughw:${idx},0"
        AUDIO_CONTROL_CARD="${idx}"
        AUDIO_PROFILE_DESC="MAX98357A (tarjeta ${idx})"
      else
        AUDIO_DEVICE_PCM="plughw:1,0"
        AUDIO_CONTROL_CARD="1"
        AUDIO_PROFILE_DESC="MAX98357A (tarjeta 1 asumida)"
        log WARN "No se detectó tarjeta MAX98357A; usando card 1"
      fi
      ;;
    vc4hdmi|hdmi)
      if idx=$(detect_card_index "vc4hdmi"); then
        AUDIO_DEVICE_PCM="plughw:${idx},0"
        AUDIO_CONTROL_CARD="${idx}"
        AUDIO_PROFILE_DESC="VC4 HDMI (tarjeta ${idx})"
      else
        AUDIO_DEVICE_PCM="plughw:0,0"
        AUDIO_CONTROL_CARD="0"
        AUDIO_PROFILE_DESC="VC4 HDMI (tarjeta 0 asumida)"
        log WARN "No se detectó tarjeta VC4HDMI; usando card 0"
      fi
      ;;
    usb)
      if idx=$(detect_card_index "usb"); then
        AUDIO_DEVICE_PCM="plughw:${idx},0"
        AUDIO_CONTROL_CARD="${idx}"
        AUDIO_PROFILE_DESC="USB Audio (tarjeta ${idx})"
      else
        AUDIO_DEVICE_PCM="plughw:0,0"
        AUDIO_CONTROL_CARD="0"
        AUDIO_PROFILE_DESC="USB Audio no encontrada (se usa tarjeta 0)"
        log WARN "No se detectó tarjeta de audio USB; usando card 0"
      fi
      ;;
    none)
      AUDIO_DEVICE_PCM=""
      AUDIO_CONTROL_CARD=""
      AUDIO_PROFILE_DESC="Perfil de audio 'none' (sin cambios)"
      ;;
    *)
      die "Perfil de audio no soportado: ${profile}"
      ;;
  esac
}

resolve_audio_profile "${AUDIO_PROFILE}"
if [[ -n "${AUDIO_DEVICE_PCM}" ]]; then
  log alsa "Perfil de audio: ${AUDIO_PROFILE_RESOLVED} → ${AUDIO_DEVICE_PCM}"
else
  log alsa "Perfil de audio: ${AUDIO_PROFILE_RESOLVED} (sin cambios en ALSA)"
fi

ensure_ld_so_conf(){
  local dir="$1"
  local conf="/etc/ld.so.conf.d/piper.conf"
  local tmp
  tmp="$(mktemp)"
  printf '%s\n' "${dir}" > "${tmp}"
  if install_if_different "${tmp}" "${conf}" 0644; then
    log piper "Registrado ${dir} en ${conf}"
  else
    log piper "${conf} ya contiene ${dir}"
  fi
  rm -f "${tmp}"
}

run_as_target(){
  local quoted_cmd
  printf -v quoted_cmd ' %q' "$@"
  su - "${TARGET_USER}" -s /bin/bash -c "${quoted_cmd}"
}

log INFO "Instalando aplicación para ${TARGET_USER}"
mkdir -p "${APP_DIR}"
if [[ "${REPO_ROOT}" != "${APP_DIR}" ]]; then
  log INFO "Sincronizando aplicación en ${APP_DIR}"
  rsync -a --delete --exclude '.venv' --exclude '.git' "${REPO_ROOT}/" "${APP_DIR}/"
fi

# Propietario correcto del repo completo
chown -R "${TARGET_USER}:audio" "${APP_DIR}"

# La cadena /home → /home/${TARGET_USER} → APP_DIR debe ser “ejecutable” (x) para poder hacer chdir
chmod 755 /home "${TARGET_HOME}" "${APP_DIR}"

# Permisos razonables dentro del repo
{
  find "${APP_DIR}" -type d -exec chmod 755 {} \;
  find "${APP_DIR}" -type f -exec chmod 644 {} \;
} || true
# Ejecutables para scripts y binarios del proyecto
chmod 755 "${APP_DIR}"/scripts/*.sh 2>/dev/null || true
# Asegurar que safe_run.sh sea ejecutable específicamente
chmod 755 "${APP_DIR}/scripts/safe_run.sh" 2>/dev/null || true

SAFE_RUN_PATH="${APP_DIR}/scripts/safe_run.sh"
if [[ ! -f "${SAFE_RUN_PATH}" ]]; then
  die "No se encontró ${SAFE_RUN_PATH}; verifica la sincronización del repositorio"
fi
if [[ ! -x "${SAFE_RUN_PATH}" ]]; then
  chmod 755 "${SAFE_RUN_PATH}"
  log INFO "Permisos de ejecución aplicados a safe_run.sh"
fi

# Crear el directorio de configuración con permisos correctos
install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_USER}" "${CFG_DIR}"

# Crear directorio de logs en el home del usuario para evitar problemas de permisos
USER_LOG_DIR="${TARGET_HOME}/.bascula/logs"
install -d -m 0755 -o "${TARGET_USER}" -g "audio" "${USER_LOG_DIR}"

# También crear el directorio del sistema como fallback
LOG_DIR="/var/log/bascula"
install -d -m 0755 "${LOG_DIR}"
if getent group audio >/dev/null 2>&1; then
  chown "${TARGET_USER}:audio" "${LOG_DIR}"
else
  chown "${TARGET_USER}:${TARGET_USER}" "${LOG_DIR}" || true
fi

VENV="${APP_DIR}/.venv"
if [[ ! -d "${VENV}" ]]; then
  log INFO "Creando entorno virtual en ${VENV}"
  run_as_target python3 -m venv "${VENV}"
else
  log INFO "Entorno virtual ya existente en ${VENV}"
fi

log INFO "Actualizando pip/setuptools/wheel"
run_as_target "${VENV}/bin/python" -m pip install --upgrade pip setuptools wheel
if [[ -f "${APP_DIR}/requirements.txt" ]]; then
  log INFO "Instalando dependencias desde requirements.txt"
  run_as_target "${VENV}/bin/python" -m pip install -r "${APP_DIR}/requirements.txt"
else
  log WARN "No se encontró requirements.txt; omitiendo instalación"
fi

log INFO "Instalando bascula-cam en modo editable"
run_as_target "${VENV}/bin/python" -m pip install -e "${APP_DIR}"

if [[ -f "${APP_DIR}/pyproject.toml" && -d "${APP_DIR}/tests" ]]; then
  echo "[test] Ejecutando pytest..."
  run_as_target "${VENV}/bin/python" -m pip install -U pytest
  if ! run_as_target "${VENV}/bin/python" -m pytest -q "${APP_DIR}/tests"; then
    echo "[warn] pytest falló (no bloquea la instalación)"
  fi
fi

SERVICE_SRC="${REPO_ROOT}/systemd/bascula-ui.service"
SERVICE_DST="/etc/systemd/system/bascula-ui.service"
if [[ ! -f "${SERVICE_SRC}" ]]; then
  die "No se encontró ${SERVICE_SRC}"
fi

# Verificar que safe_run.sh existe antes de instalar el servicio
if [[ ! -f "${APP_DIR}/scripts/safe_run.sh" ]]; then
  die "No se encontró ${APP_DIR}/scripts/safe_run.sh requerido por el servicio"
fi

log INFO "Instalando servicio systemd bascula-ui.service"
install -m 0644 "${SERVICE_SRC}" "${SERVICE_DST}"

# Crear directorios de logs si no existen
install -d -m 0755 /var/log/bascula
chown "${TARGET_USER}:audio" /var/log/bascula

# Asegurar que el directorio de logs del usuario existe
install -d -m 0755 -o "${TARGET_USER}" -g "audio" "${TARGET_HOME}/.bascula/logs"

if systemctl list-unit-files | grep -q '^ocr-service.service'; then
  systemctl reset-failed ocr-service.service || true
fi
systemctl reset-failed bascula-ui.service 2>/dev/null || true

TMPDIR="$(mktemp -d)"
trap 'rm -rf "${TMPDIR}"' EXIT
ARCH="$(uname -m)"
ASSET=""
case "${ARCH}" in
  aarch64|arm64)
    ASSET="piper_linux_aarch64.tar.gz"
    ;;
  armv7l|arm)
    ASSET="piper_armv7l.tar.gz"
    ;;
  x86_64)
    ASSET="piper_linux_x86_64.tar.gz"
    ;;
  *)
    log WARN "Arquitectura ${ARCH} no soportada para Piper"
    ;;
esac
if [[ -n "${ASSET}" ]]; then
  PIPER_URL="https://github.com/rhasspy/piper/releases/latest/download/${ASSET}"
  log piper "Descargando Piper (${ASSET}) desde ${PIPER_URL}"
  curl -fSL --retry 3 --retry-delay 2 -o "${TMPDIR}/piper.tgz" "${PIPER_URL}"
  tar -xzf "${TMPDIR}/piper.tgz" -C "${TMPDIR}"
  PIPER_BIN="$(find "${TMPDIR}" -type f -name piper -perm -111 | head -n1 || true)"
  [[ -n "${PIPER_BIN}" ]] || die "No se encontró ejecutable 'piper' tras extraer"
  PIPER_ROOT="$(dirname "${PIPER_BIN}")"
  PIPER_INSTALL_DIR="/usr/local/lib/piper"
  install -d -m 0755 "${PIPER_INSTALL_DIR}"
  install -m 0755 "${PIPER_BIN}" "${PIPER_INSTALL_DIR}/piper"
  log piper "Binario instalado en ${PIPER_INSTALL_DIR}/piper"
  libs_copied=false
  if [[ -d "${PIPER_ROOT}/lib" ]]; then
    cp -a "${PIPER_ROOT}/lib/." "${PIPER_INSTALL_DIR}/"
    libs_copied=true
  else
    while IFS= read -r -d '' libfile; do
      cp -a "${libfile}" "${PIPER_INSTALL_DIR}/"
      libs_copied=true
    done < <(find "${TMPDIR}" \( -xtype f -o -xtype l \) -name 'lib*.so*' -print0)
  fi
  if [[ "${libs_copied}" == "true" ]]; then
    log piper "Bibliotecas copiadas a ${PIPER_INSTALL_DIR}"
  else
    log piper "No se encontraron bibliotecas adicionales en el paquete"
  fi
  ensure_ld_so_conf "${PIPER_INSTALL_DIR}"
  if command -v patchelf >/dev/null 2>&1; then
    if patchelf --set-rpath "${PIPER_INSTALL_DIR}" "${PIPER_INSTALL_DIR}/piper"; then
      log piper "RPATH fijado a ${PIPER_INSTALL_DIR}"
    else
      log piper "No se pudo fijar RPATH con patchelf"
    fi
  else
    log piper "patchelf no disponible; se omite RPATH"
  fi
  cat <<'WRAPPER' > "${TMPDIR}/piper-wrapper"
#!/usr/bin/env bash
set -euo pipefail

export ESPEAK_DATA_PATH="${ESPEAK_DATA_PATH:-/usr/share/espeak-ng-data}"
exec "/usr/local/lib/piper/piper" "$@"
WRAPPER
  install -m 0755 "${TMPDIR}/piper-wrapper" /usr/local/bin/piper
  log piper "Wrapper /usr/local/bin/piper actualizado"
  ldconfig
  log piper "ldconfig ejecutado"
else
  log WARN "No se determinó asset de Piper para ${ARCH}"
fi

if [[ -n "${AUDIO_DEVICE_PCM}" ]]; then
  ensure_asound_conf "${AUDIO_DEVICE_PCM}" "${AUDIO_CONTROL_CARD}" "${AUDIO_PROFILE_DESC}"
  ensure_service_audio_dropin "${AUDIO_DEVICE_PCM}" "${AUDIO_PROFILE_DESC}"
else
  ensure_service_audio_dropin "" ""
  log alsa "Perfil de audio 'none': se mantiene /etc/asound.conf existente"
fi

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

echo "[diag] Comprobando cadena de permisos para ${APP_DIR}"
ls -ld /home "${TARGET_HOME}" "${APP_DIR}" || true
namei -om "${APP_DIR}" || true
sudo -u "${TARGET_USER}" test -x "${APP_DIR}" \
  && echo "[diag] ${TARGET_USER} puede hacer chdir a APP_DIR" \
  || echo "[diag] ERROR: ${TARGET_USER} no puede chdir a APP_DIR"

set -e

systemctl daemon-reload

# Verificar que el archivo de servicio se instaló correctamente
if [[ ! -f "${SERVICE_DST}" ]]; then
  die "El archivo de servicio no se instaló correctamente en ${SERVICE_DST}"
fi

# Configurar X11 para el usuario
log INFO "Configurando X11 para ${TARGET_USER}"

# Instalar servicios kiosk-xorg
log INFO "Instalando servicio kiosk-xorg"
install -m 0644 "${REPO_ROOT}/systemd/kiosk-xorg.service" "/etc/systemd/system/"

# Instalar xinitrc personalizado
install -d -m 0755 /etc/X11/xinit
install -m 0755 "${REPO_ROOT}/etc/X11/xinit/xinitrc" "/etc/X11/xinit/xinitrc"

# Habilitar kiosk-xorg
systemctl enable kiosk-xorg.service

if [[ -n "${DISPLAY:-}" ]]; then
  # Permitir acceso X11 al usuario
  xhost +local:"${TARGET_USER}" 2>/dev/null || true
  
  # Asegurar que .Xauthority existe y tiene permisos correctos
  if [[ -f "${TARGET_HOME}/.Xauthority" ]]; then
    chown "${TARGET_USER}:${TARGET_USER}" "${TARGET_HOME}/.Xauthority"
    chmod 600 "${TARGET_HOME}/.Xauthority"
  fi
fi

log INFO "Habilitando e iniciando bascula-ui.service"
systemctl enable bascula-ui.service

# Verificar que el script safe_run.sh es ejecutable por el usuario target
if ! run_as_target test -x "${APP_DIR}/scripts/safe_run.sh"; then
  log WARN "safe_run.sh no es ejecutable por ${TARGET_USER}, corrigiendo..."
  chmod 755 "${APP_DIR}/scripts/safe_run.sh"
fi

# Esperar un momento antes de iniciar el servicio
sleep 2
systemctl start bascula-ui.service
sleep 3

if ! systemctl is-active --quiet bascula-ui.service; then
  echo "[err] bascula-ui inactivo"
  echo "[diag] Verificando rutas y permisos:"
  namei -om "${APP_DIR}" || true
  ls -la "${APP_DIR}/scripts/safe_run.sh" || true
  echo "[diag] Logs del servicio:"
  journalctl -u bascula-ui -n 50 --no-pager || true
  echo "[diag] Estado del servicio:"
  systemctl status bascula-ui.service --no-pager || true
  exit 1
fi
echo "[ok] bascula-ui.service activo"

log INFO "Fase 2 completada"

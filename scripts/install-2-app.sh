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
      xserver-xorg \
      xserver-xorg-input-all \
      xserver-xorg-video-fbdev \
      xinit \
      x11-xserver-utils \
      unclutter \
      unclutter-xfixes \
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

# CONFIGURACIÓN DEL ARRANQUE KIOSCO (AUTOLOGIN + STARTX)
if [[ -n "${AUDIO_DEVICE_PCM}" ]]; then
  ensure_asound_conf "${AUDIO_DEVICE_PCM}" "${AUDIO_CONTROL_CARD}" "${AUDIO_PROFILE_DESC}"
else
  log alsa "Perfil de audio 'none': se mantiene /etc/asound.conf existente"
fi

log INFO "Configurando arranque en modo kiosco (autologin + startx)"

override_dir="/etc/systemd/system/getty@tty1.service.d"
override_conf="${override_dir}/override.conf"
tmp_file="$(mktemp)"
cat <<EOF > "${tmp_file}"
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin ${TARGET_USER} --noclear %I \$TERM
Type=idle
EOF
install -d -m 0755 "${override_dir}"
if install_if_different "${tmp_file}" "${override_conf}" 0644; then
  log kiosk "Autologin configurado en tty1 para ${TARGET_USER}"
else
  log kiosk "Autologin en tty1 ya estaba configurado"
fi
rm -f "${tmp_file}"

bash_profile="${TARGET_HOME}/.bash_profile"
tmp_file="$(mktemp)"
cat <<'PROFILE' > "${tmp_file}"
# Arranca Xorg automáticamente si estamos en tty1 y no hay sesión gráfica
if [[ -z "$DISPLAY" ]] && [[ "$(tty)" == "/dev/tty1" ]]; then
  exec startx
fi
PROFILE
if install_if_different "${tmp_file}" "${bash_profile}" 0644; then
  log kiosk "Actualizado ${bash_profile}"
else
  log kiosk "${bash_profile} ya estaba configurado"
fi
chown "${TARGET_USER}:${TARGET_USER}" "${bash_profile}" || true
rm -f "${tmp_file}"

xinitrc="${TARGET_HOME}/.xinitrc"
tmp_file="$(mktemp)"
cat <<EOF > "${tmp_file}"
#!/bin/sh
# Desactivar salvapantallas y gestión de energía
xset s off -dpms

# Ocultar el cursor del ratón
unclutter -idle 1 -root &

# Ejecutar el script de arranque seguro de la aplicación
exec "${APP_DIR}/scripts/safe_run.sh" >> "${TARGET_HOME}/bascula_app.log" 2>&1
EOF
if install_if_different "${tmp_file}" "${xinitrc}" 0755; then
  log kiosk "Actualizado ${xinitrc}"
else
  log kiosk "${xinitrc} ya estaba configurado"
fi
chown "${TARGET_USER}:${TARGET_USER}" "${xinitrc}" || true
rm -f "${tmp_file}"

systemctl daemon-reload
systemctl restart "getty@tty1.service" || true

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

log INFO "Fase 2 completada"

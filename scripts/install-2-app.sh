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

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  die "Este script debe ejecutarse con sudo o como root"
fi

if ! id "${TARGET_USER}" >/dev/null 2>&1; then
  die "El usuario objetivo '${TARGET_USER}' no existe"
fi
if [[ -z "${TARGET_HOME}" ]]; then
  die "No se pudo determinar el directorio home de ${TARGET_USER}"
fi

install_if_different(){
  local src="$1" dest="$2" mode="$3"
  if [[ -f "${dest}" ]] && cmp -s "${src}" "${dest}"; then
    return 1
  fi
  install -m "${mode}" "${src}" "${dest}"
  return 0
}

ensure_asound_conf(){
  local asound_conf="/etc/asound.conf"
  local tmp
  tmp="$(mktemp)"
  cat <<'ASOUND' > "${tmp}"
pcm.!default {
    type plug
    slave.pcm "softvol"
}

pcm.softvol {
    type softvol
    slave {
        pcm "plughw:1,0"
    }
    control {
        name "SoftMaster"
        card 1
    }
    min_dB -51.0
    max_dB 0.0
}

ctl.!default {
    type hw
    card 1
}
ASOUND
  if install_if_different "${tmp}" "${asound_conf}" 0644; then
    log alsa "Configurado /etc/asound.conf para salida plughw:1,0 con softvol"
  else
    log alsa "/etc/asound.conf ya estaba configurado para plughw:1,0"
  fi
  rm -f "${tmp}"
}

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
chown -R "${TARGET_USER}:${TARGET_USER}" "${APP_DIR}" || true

# La cadena /home → /home/pi → /home/pi/bascula-cam debe ser “ejecutable” (x) para poder hacer chdir
chmod 755 /home || true
chmod 755 "${TARGET_HOME}" || true
chmod 755 "${APP_DIR}" || true

# Permisos razonables dentro del repo
find "${APP_DIR}" -type d -exec chmod 755 {} \; || true
find "${APP_DIR}" -type f -exec chmod 644 {} \; || true
# Ejecutables para scripts y binarios del proyecto
chmod 755 "${APP_DIR}"/scripts/*.sh 2>/dev/null || true

# Crear el directorio de configuración con permisos correctos
install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_USER}" "${CFG_DIR}"

VENV_PATH="${APP_DIR}/.venv"
if [[ ! -d "${VENV_PATH}" ]]; then
  log INFO "Creando entorno virtual en ${VENV_PATH}"
  run_as_target python3 -m venv "${VENV_PATH}"
else
  log INFO "Entorno virtual ya existente en ${VENV_PATH}"
fi

log INFO "Actualizando pip/setuptools/wheel"
run_as_target "${VENV_PATH}/bin/python" -m pip install --upgrade pip setuptools wheel
if [[ -f "${APP_DIR}/requirements.txt" ]]; then
  log INFO "Instalando dependencias desde requirements.txt"
  run_as_target "${VENV_PATH}/bin/python" -m pip install -r "${APP_DIR}/requirements.txt"
else
  log WARN "No se encontró requirements.txt; omitiendo instalación"
fi

SERVICE_SRC="${APP_DIR}/systemd/bascula-ui.service"
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

ensure_asound_conf

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

systemctl daemon-reload
systemctl enable --now bascula-ui.service
sleep 2
if ! systemctl is-active --quiet bascula-ui.service; then
  echo "[err] bascula-ui.service inactivo. Mostrando diagnóstico…"
  ls -ld /home "${TARGET_HOME}" "${APP_DIR}" || true
  namei -om "${APP_DIR}" || true
  journalctl -u bascula-ui -n 150 --no-pager || true
  exit 1
fi
echo "[ok] bascula-ui.service activo"
set -e

log INFO "Fase 2 completada"

#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  exec sudo -E OTA_SOURCE="${OTA_SOURCE:-}" bash "$0" "$@"
fi

LOG_DIR="/var/log/bascula"
LOG_FILE="${LOG_DIR}/ota.log"
mkdir -p "${LOG_DIR}"
: "${OTA_SOURCE:=}"

if ! touch "${LOG_FILE}" >/dev/null 2>&1; then
  echo "[ota] No se pudo abrir ${LOG_FILE}" >&2
  exit 1
fi

exec > >(tee -a "${LOG_FILE}") 2>&1

log() {
  local ts
  ts="$(date --iso-8601=seconds 2>/dev/null || date)"
  printf '[ota][%s] %s\n' "${ts}" "$*"
}

fail() {
  log "ERROR: $*"
  return 1
}

usage() {
  cat <<'USAGE'
Uso: ota.sh [fuente]
  fuente puede ser:
    - Ruta a un archivo .tar.gz/.tgz/.tar/.zip
    - Ruta a un directorio con el contenido de la release
    - URL http(s) a un archivo comprimido
  Si no se especifica, se utilizará la variable OTA_SOURCE.
USAGE
}

SOURCE="${1:-${OTA_SOURCE}}"
if [[ -z "${SOURCE}" ]]; then
  usage >&2
  exit 1
fi

BASCULA_ROOT="/opt/bascula"
RELEASES_DIR="${BASCULA_ROOT}/releases"
CURRENT_LINK="${BASCULA_ROOT}/current"
SHARED_DIR="${BASCULA_ROOT}/shared"
FORCE_FLAG="${BASCULA_ROOT}/shared/userdata/force_recovery"
FAIL_COUNT_FILE="${BASCULA_ROOT}/shared/userdata/app_fail_count"

if [[ -f /etc/default/bascula ]]; then
  # shellcheck disable=SC1091
  source /etc/default/bascula
fi
BASCULA_USER="${BASCULA_USER:-pi}"
BASCULA_GROUP="${BASCULA_GROUP:-${BASCULA_USER}}"

have_systemd() {
  command -v systemctl >/dev/null 2>&1 && [[ -d /run/systemd/system ]]
}

stop_services() {
  if have_systemd; then
    systemctl stop bascula-app.service bascula-web.service bascula-recovery.service >/dev/null 2>&1 || true
  fi
}

start_services() {
  if have_systemd; then
    systemctl daemon-reload || true
    systemctl reset-failed bascula-app.service bascula-web.service >/dev/null 2>&1 || true
    systemctl start bascula-web.service || true
    systemctl start bascula-app.service || true
  fi
}

wait_for_service() {
  local unit="$1" timeout="$2" elapsed=0
  if ! have_systemd; then
    return 0
  fi
  while (( elapsed < timeout )); do
    if systemctl is-active --quiet "$unit"; then
      return 0
    fi
    sleep 1
    ((elapsed++))
  done
  return 1
}

check_web_health() {
  local url="${HEALTH_URL:-http://127.0.0.1:8080/health}" attempts=30
  if ! command -v curl >/dev/null 2>&1; then
    log "curl no disponible para healthcheck"
    return 0
  fi
  for ((i=1; i<=attempts; i++)); do
    if curl -fsS --max-time 5 "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  return 1
}

TMP_DIR=""
STAGING_DIR=""
NEW_RELEASE_DIR=""
PREVIOUS_RELEASE=""

cleanup() {
  if [[ -n "${TMP_DIR}" && -d "${TMP_DIR}" ]]; then
    rm -rf "${TMP_DIR}"
  fi
}
trap cleanup EXIT

prepare_staging() {
  local src="$1"
  TMP_DIR="$(mktemp -d)"
  local work="${TMP_DIR}/work"
  mkdir -p "${work}"

  if [[ "$src" =~ ^https?:// ]]; then
    local archive="${TMP_DIR}/package"
    log "Descargando release desde ${src}"
    if command -v curl >/dev/null 2>&1; then
      if ! curl -fL --retry 3 --retry-delay 2 -o "${archive}" "$src"; then
        fail "Descarga falló desde ${src}" || return 1
      fi
    elif command -v wget >/dev/null 2>&1; then
      if ! wget -O "${archive}" "$src"; then
        fail "Descarga falló desde ${src}" || return 1
      fi
    else
      fail "No se encontró curl ni wget para descargar" || return 1
    fi
    src="${archive}"
  fi

  if [[ -f "$src" ]]; then
    log "Extrayendo ${src}"
    if ! tar -xaf "$src" -C "${work}" 2>/dev/null; then
      if command -v unzip >/dev/null 2>&1; then
        if ! unzip -q "$src" -d "${work}"; then
          fail "No se pudo extraer el archivo ${src}" || return 1
        fi
      else
        fail "No se pudo extraer el archivo ${src}" || return 1
      fi
    fi
  elif [[ -d "$src" ]]; then
    log "Copiando contenido desde directorio ${src}"
    rsync -a "$src"/ "${work}"/ || {
      fail "No se pudo copiar el directorio ${src}" || return 1
    }
  else
    fail "Fuente ${src} no encontrada" || return 1
  fi

  local first
  first="$(find "${work}" -mindepth 1 -maxdepth 1 -type d -print -quit)"
  if [[ -n "$first" ]]; then
    STAGING_DIR="$first"
  else
    STAGING_DIR="${work}"
  fi
}

ensure_shared_links() {
  local release_dir="$1" name dest shared_path
  install -d -m 0755 -o "${BASCULA_USER}" -g "${BASCULA_GROUP}" "${SHARED_DIR}" || true
  for name in assets voices-v1 ota models userdata config; do
    shared_path="${SHARED_DIR}/${name}"
    dest="${release_dir}/${name}"
    install -d -m 0755 -o "${BASCULA_USER}" -g "${BASCULA_GROUP}" "${shared_path}" || true
    if [[ -e "${dest}" && ! -L "${dest}" ]]; then
      rm -rf "${dest}"
    fi
    if [[ ! -e "${dest}" ]]; then
      ln -s "${shared_path}" "${dest}"
    fi
  done
}

migrate_venv() {
  local old_release="$1" new_release="$2"
  if [[ -d "${old_release}/.venv" && ! -e "${new_release}/.venv" ]]; then
    log "Migrando entorno virtual desde release anterior"
    rsync -a "${old_release}/.venv/" "${new_release}/.venv/" || {
      fail "No se pudo migrar el entorno virtual" || return 1
    }
  fi
}

update_requirements() {
  local release_dir="$1" pip_bin="${release_dir}/.venv/bin/pip"
  if [[ -x "${pip_bin}" && -f "${release_dir}/requirements.txt" ]]; then
    log "Actualizando dependencias"
    if ! PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore PIP_PREFER_BINARY=1 \
      "${pip_bin}" install --upgrade -r "${release_dir}/requirements.txt"; then
      fail "pip install falló" || return 1
    fi
  fi
  return 0
}

reset_failure_state() {
  rm -f "${FORCE_FLAG}" "${FAIL_COUNT_FILE}" 2>/dev/null || true
}

rollback() {
  local new_dir="$1"
  log "Iniciando rollback"
  stop_services
  if [[ -n "${PREVIOUS_RELEASE}" ]]; then
    ln -sfn "${PREVIOUS_RELEASE}" "${CURRENT_LINK}"
    log "Restaurado enlace a ${PREVIOUS_RELEASE}"
    start_services
  fi
  if [[ -n "${new_dir}" && -d "${new_dir}" ]]; then
    mv "${new_dir}" "${new_dir}.failed" 2>/dev/null || rm -rf "${new_dir}" || true
  fi
}

main() {
  prepare_staging "${SOURCE}"
  install -d -m 0755 "${RELEASES_DIR}"
  local timestamp
  timestamp="$(date +%Y%m%d%H%M%S)"
  NEW_RELEASE_DIR="${RELEASES_DIR}/${timestamp}"
  log "Creando release ${NEW_RELEASE_DIR}"
  install -d -m 0755 "${NEW_RELEASE_DIR}"

  local rsync_rc=0
  rsync -a --delete \
    --exclude '.git' \
    --exclude '.venv' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude 'shared/models' \
    --exclude 'shared/userdata' \
    --exclude 'shared/config' \
    "${STAGING_DIR}/" "${NEW_RELEASE_DIR}/" || rsync_rc=$?
  if [[ ${rsync_rc} -ne 0 && ${rsync_rc} -ne 23 && ${rsync_rc} -ne 24 ]]; then
    fail "rsync falló con código ${rsync_rc}" || return 1
  fi

  PREVIOUS_RELEASE="$(readlink -f "${CURRENT_LINK}" 2>/dev/null || true)"
  if [[ -n "${PREVIOUS_RELEASE}" ]]; then
    migrate_venv "${PREVIOUS_RELEASE}" "${NEW_RELEASE_DIR}"
  fi

  if [[ ! -x "${NEW_RELEASE_DIR}/.venv/bin/python" ]]; then
    log "Creando nuevo entorno virtual"
    python3 -m venv "${NEW_RELEASE_DIR}/.venv" || {
      fail "python -m venv falló" || return 1
    }
  fi

  ensure_shared_links "${NEW_RELEASE_DIR}"

  chown -R "${BASCULA_USER}:${BASCULA_GROUP}" "${NEW_RELEASE_DIR}"

  update_requirements "${NEW_RELEASE_DIR}" || return 1

  stop_services
  ln -sfn "${NEW_RELEASE_DIR}" "${CURRENT_LINK}"
  log "/opt/bascula/current -> ${NEW_RELEASE_DIR}"
  reset_failure_state
  start_services

  if ! wait_for_service bascula-web.service 40; then
    fail "bascula-web.service no se activó" || return 1
  fi
  if ! wait_for_service bascula-app.service 60; then
    fail "bascula-app.service no se activó" || return 1
  fi
  if ! check_web_health; then
    fail "Healthcheck de bascula-web falló" || return 1
  fi
  log "Healthcheck web OK"
  log "OTA completada exitosamente"
}

if ! main; then
  rc=$?
  log "OTA falló (rc=${rc})"
  rollback "${NEW_RELEASE_DIR}"
  exit "$rc"
fi

exit 0

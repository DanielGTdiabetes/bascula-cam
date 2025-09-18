#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_BRANCH="main"
LOG_FILE="/var/log/bascula/ota.log"
LOCK_FILE="/var/run/bascula-ota.lock"
TARGET_USER="${TARGET_USER:-pi}"

mkdir -p "$(dirname "${LOG_FILE}")"
touch "${LOG_FILE}"
chmod 0644 "${LOG_FILE}" || true
mkdir -p "/var/run"

declare FAIL_REASON=""
cleanup() {
  local status=$?
  if [[ -n "${LOCK_FD:-}" ]]; then
    flock -u "${LOCK_FD}" || true
    eval "exec ${LOCK_FD}>&-"
  fi
  if (( status != 0 )); then
    local msg=${FAIL_REASON:-"Error inesperado (código ${status})"}
    printf 'OTA_FAIL:%s\n' "$msg"
  fi
}
trap cleanup EXIT

exec {LOCK_FD}>"${LOCK_FILE}"
if ! flock -n "${LOCK_FD}"; then
  FAIL_REASON="Otra actualización OTA está en curso"
  exit 1
fi

declare mode="stash"
declare branch="${DEFAULT_BRANCH}"

usage() {
  cat <<USAGE
Uso: ${0##*/} [--stash|--force] [--branch=NOMBRE]
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --stash)
      mode="stash"
      ;;
    --force)
      mode="force"
      ;;
    --branch=*)
      branch="${1#*=}"
      ;;
    --branch)
      shift
      [[ $# -gt 0 ]] || { FAIL_REASON="Falta nombre de rama"; exit 1; }
      branch="$1"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      FAIL_REASON="Parámetro desconocido: $1"
      exit 1
      ;;
  esac
  shift
done

log() {
  printf '[ota] %s\n' "$*"
}

fail() {
  FAIL_REASON="$1"
  exit 1
}

exec > >(tee -a "${LOG_FILE}") 2>&1
log "Iniciando OTA (modo=${mode}, rama=${branch})"

command -v git >/dev/null 2>&1 || fail "git no está instalado"
command -v curl >/dev/null 2>&1 || fail "curl no está instalado"
command -v tar >/dev/null 2>&1 || fail "tar no está instalado"

[[ -d "${REPO}/.git" ]] || fail "Repositorio no encontrado en ${REPO}"

log "Comprobando conectividad"
if ! curl -Is --max-time 10 https://github.com >/dev/null 2>&1; then
  fail "Sin acceso a https://github.com"
fi

log "Comprobando espacio libre"
avail_kb=$(df -Pk "${REPO}" 2>/dev/null | awk 'NR==2 {print $4}')
if [[ -z "${avail_kb}" || ${avail_kb} -lt 300000 ]]; then
  fail "Espacio insuficiente en ${REPO}"
fi

if ! git -C "${REPO}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  fail "${REPO} no es un repositorio git válido"
fi

status_output=$(git -C "${REPO}" status --porcelain)
if [[ -n "${status_output}" ]]; then
  log "Repositorio con cambios locales"
  mkdir -p "${REPO}/logs" "${REPO}/backups"
  patch_file="${REPO}/logs/local.patch"
  backup_file="${REPO}/backups/working-tree-$(date +%F-%H%M%S).tgz"
  git -C "${REPO}" diff > "${patch_file}" || log "No se pudo generar diff local"
  tar -czf "${backup_file}" -C "${REPO}" . || log "No se pudo crear backup"
  if [[ "${mode}" == "force" ]]; then
    log "Descartando cambios locales (force)"
    git -C "${REPO}" reset --hard || fail "git reset --hard falló"
    git -C "${REPO}" clean -fdx || fail "git clean falló"
  else
    stash_msg="ota-$(date +%F-%H%M%S)"
    git -C "${REPO}" stash push -u -m "${stash_msg}" || fail "git stash falló"
  fi
fi

log "Sincronizando con origen"
git -C "${REPO}" fetch --all --prune || fail "git fetch falló"
git -C "${REPO}" reset --hard "origin/${branch}" || fail "git reset --hard origin/${branch} falló"

log "Ejecutando fase 2 del instalador"
if ! sudo TARGET_USER="${TARGET_USER}" APP_DIR="${REPO}" bash "${REPO}/scripts/install-2-app.sh" --resume; then
  fail "install-2-app.sh falló"
fi

short_commit=$(git -C "${REPO}" rev-parse --short HEAD)
log "OTA completada (${short_commit})"
trap - EXIT
printf 'OTA_OK:%s:%s\n' "${branch}" "${short_commit}"

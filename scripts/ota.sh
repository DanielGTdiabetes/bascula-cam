#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_BRANCH="main"
LOG_FILE="/var/log/bascula/ota.log"

mkdir -p "$(dirname "${LOG_FILE}")"

declare FAIL_REASON=""

cleanup() {
  local status=$?
  if (( status != 0 )); then
    local message=${FAIL_REASON:-"Error inesperado (código ${status})"}
    printf 'OTA_FAIL:%s\n' "$message"
  fi
}
trap cleanup EXIT

exec > >(tee -a "$LOG_FILE") 2>&1

declare mode="stash"
declare branch="$DEFAULT_BRANCH"

usage() {
  cat <<USAGE
Uso: ${0##*/} [--stash|--force] [--branch=BR]

  --stash      Guarda los cambios locales en git stash antes de actualizar (por defecto)
  --force      Descarta los cambios locales con reset --hard y clean -fdx
  --branch=BR  Rama a sincronizar (por defecto: ${DEFAULT_BRANCH})
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
      if [[ $# -eq 0 ]]; then
        FAIL_REASON="Falta el nombre de la rama para --branch"
        exit 1
      fi
      branch="$1"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      FAIL_REASON="Parámetro desconocido: $1"
      usage
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

log "Iniciando actualización OTA (modo=${mode}, rama=${branch})"

if ! command -v git >/dev/null 2>&1; then
  fail "git no está disponible"
fi
if ! command -v curl >/dev/null 2>&1; then
  fail "curl no está disponible"
fi
if ! command -v tar >/dev/null 2>&1; then
  fail "tar no está disponible"
fi
if [[ ! -d "${REPO}/.git" ]]; then
  fail "Repositorio no encontrado en ${REPO}"
fi

log "Verificando conectividad a GitHub"
if ! curl -Is --max-time 10 https://github.com >/dev/null 2>&1; then
  fail "Sin conectividad a https://github.com"
fi

log "Verificando espacio libre en /home"
avail_kb=$(df -Pk /home 2>/dev/null | awk 'NR==2 {print $4}')
if [[ -z "${avail_kb}" ]]; then
  fail "No se pudo determinar espacio libre en /home"
fi
if (( avail_kb < 300 * 1024 )); then
  fail "Espacio insuficiente en /home (<300MB)"
fi

if ! git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  fail "Directorio ${REPO} no es un repositorio git válido"
fi

status_output=$(git -C "$REPO" status --porcelain)
if [[ -n "${status_output}" ]]; then
  log "Repositorio con cambios locales, creando respaldos"
  mkdir -p /home/pi/bascula-cam/logs /home/pi/bascula-cam/backups
  patch_file="/home/pi/bascula-cam/logs/local.patch"
  backup_file="/home/pi/bascula-cam/backups/working-tree-$(date +%F-%H%M%S).tgz"
  if ! git -C "$REPO" diff >"${patch_file}"; then
    fail "No se pudo crear diff local en ${patch_file}"
  fi
  if ! tar -czf "${backup_file}" -C "$REPO" .; then
    fail "No se pudo crear respaldo ${backup_file}"
  fi
  log "Respaldos guardados en ${patch_file} y ${backup_file}"
  if [[ "${mode}" == "force" ]]; then
    log "Descartando cambios locales (reset --hard + clean)"
    if ! git -C "$REPO" reset --hard "origin/${branch}"; then
      fail "git reset --hard origin/${branch} falló"
    fi
    if ! git -C "$REPO" clean -fdx; then
      fail "git clean -fdx falló"
    fi
  else
    stash_message="ota-$(date +%F-%H%M%S)"
    log "Guardando cambios en git stash (${stash_message})"
    if ! git -C "$REPO" stash push -u -m "$stash_message"; then
      fail "git stash falló"
    fi
  fi
else
  log "Repositorio limpio"
fi

log "Actualizando repositorio"
if ! git -C "$REPO" fetch --all --prune; then
  fail "git fetch falló"
fi
if ! git -C "$REPO" reset --hard "origin/${branch}"; then
  fail "git reset --hard origin/${branch} falló"
fi

log "Ejecutando fase 2 del instalador"
if ! sudo TARGET_USER=pi bash "$REPO/scripts/install-2-app.sh" --resume; then
  fail "Fase 2 del instalador falló"
fi

short_commit=$(git -C "$REPO" rev-parse --short HEAD)
log "Actualización completada en ${branch} (${short_commit})"

trap - EXIT
printf 'OTA_OK:%s:%s\n' "$branch" "$short_commit"
exit 0

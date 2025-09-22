#!/usr/bin/env bash
set -euo pipefail

OTA_SCRIPT="${OTA_SCRIPT:-/opt/bascula/current/scripts/ota.sh}"
OTA_DIR="${OTA_DIR:-/opt/bascula/shared/ota}"

log() { printf '[recovery-update] %s\n' "$*"; }

detect_source() {
  local latest_archive latest_dir
  if [[ -d "${OTA_DIR}" ]]; then
    latest_archive=$(find "${OTA_DIR}" -maxdepth 1 -type f \
      \( -name '*.tar.gz' -o -name '*.tgz' -o -name '*.tar' -o -name '*.zip' \) \
      -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n1 | awk '{print $2}')
    latest_dir=$(find "${OTA_DIR}" -maxdepth 1 -mindepth 1 -type d -print -quit 2>/dev/null || true)
  fi
  if [[ -n "${latest_archive}" ]]; then
    printf '%s' "${latest_archive}"
    return 0
  fi
  if [[ -n "${latest_dir}" ]]; then
    printf '%s' "${latest_dir}"
    return 0
  fi
  return 1
}

select_source() {
  local source="${1:-}" fallback
  if [[ -n "${source}" ]]; then
    printf '%s' "${source}"
    return 0
  fi
  if fallback="$(detect_source)"; then
    printf '%s' "${fallback}"
    return 0
  fi
  return 1
}

main() {
  if [[ ! -x "${OTA_SCRIPT}" ]]; then
    log "No se encontró ${OTA_SCRIPT}"
    exit 1
  fi

  local requested="${1:-${OTA_SOURCE:-}}" source
  if ! source="$(select_source "${requested}")"; then
    log "No se encontró paquete OTA en ${OTA_DIR}"
    exit 1
  fi
  log "Utilizando fuente OTA: ${source}"

  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    exec sudo -E OTA_SOURCE="${source}" "${OTA_SCRIPT}" "${source}"
  fi

  exec "${OTA_SCRIPT}" "${source}"
}

main "$@"

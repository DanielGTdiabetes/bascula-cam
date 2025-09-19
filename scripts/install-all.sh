#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_USER="${TARGET_USER:-pi}"
APP_DIR="${APP_DIR:-}"

log() { printf '[inst] %s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*"; }
err() { printf '[err] %s\n' "$*" >&2; }

usage() {
  cat <<'USAGE'
Uso: install-all.sh [--skip-system]

  --skip-system  Omite install-1-system.sh y ejecuta solo la fase de aplicación
USAGE
  exit "${1:-0}"
}

SKIP_SYSTEM=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-system)
      SKIP_SYSTEM=true
      ;;
    -h|--help)
      usage 0
      ;;
    *)
      err "Opción no reconocida: $1"
      usage 1
      ;;
  esac
  shift
done

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  err "Este script debe ejecutarse como root"
  exit 1
fi

if ! ${SKIP_SYSTEM} && [[ -x "${SCRIPT_DIR}/install-1-system.sh" ]]; then
  log "Ejecutando fase de sistema (sin reinicio automático)"
  TARGET_USER="${TARGET_USER}" APP_DIR="${APP_DIR}" "${SCRIPT_DIR}/install-1-system.sh" --skip-reboot || warn "install-1-system.sh reportó errores"
else
  warn "Fase de sistema omitida"
fi

log "Ejecutando fase de aplicación"
TARGET_USER="${TARGET_USER}" APP_DIR="${APP_DIR}" "${SCRIPT_DIR}/install-2-app.sh"
log "Instalación completa"
printf 'Reinicia manualmente si usas kiosk-xorg\n'

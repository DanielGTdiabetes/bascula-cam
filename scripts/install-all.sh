#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PHASE_FILE="/var/lib/bascula/phase"

log() { printf '[inst] %s\n' "$*"; }
err() { printf '[err] %s\n' "$*" >&2; }

usage() {
  cat <<'USAGE'
Uso: scripts/install-all.sh

Orquesta la instalación completa en dos fases con reinicio intermedio.
Ejecuta install-1-system.sh en la primera invocación y, tras el reinicio,
completa la configuración mediante install-2-app.sh.
USAGE
  exit "${1:-0}"
}

if [[ $# -gt 0 ]]; then
  case "$1" in
    -h|--help)
      usage 0
      ;;
    *)
      err "Opción no reconocida: $1"
      usage 1
      ;;
  esac
fi

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  err "Este script debe ejecutarse como root"
  exit 1
fi

current_phase="NONE"
if [[ -f "${PHASE_FILE}" ]]; then
  phase_value=$(grep -E '^PHASE=' "${PHASE_FILE}" | tail -n1 | cut -d= -f2- || true)
  if [[ -n "${phase_value}" ]]; then
    current_phase="${phase_value}"
  fi
fi

case "${current_phase}" in
  2_DONE)
    log "La instalación completa ya se ejecutó (PHASE=2_DONE)"
    exit 0
    ;;
  1_DONE)
    log "Detectada fase 1 completada. Ejecutando fase 2"
    "${SCRIPT_DIR}/install-2-app.sh" --resume
    exit 0
    ;;
  *)
    log "Iniciando fase 1 (sistema + hardware)"
    "${SCRIPT_DIR}/install-1-system.sh" --from-all
    ;;
esac

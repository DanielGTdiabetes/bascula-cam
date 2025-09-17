#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log() { printf '[inst] %s\n' "$*"; }
err() { printf '[err] %s\n' "$*" >&2; }

usage() {
  cat <<'USAGE'
Uso: scripts/install-all.sh [opciones fase1]

Ejecuta la instalación completa en dos fases con reinicio intermedio.
Las opciones proporcionadas se pasan a install-1-system.sh.
USAGE
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage 0
      ;;
    *)
      break
      ;;
  esac
  shift
done

log "Iniciando fase 1 (sistema + hardware)"
"${SCRIPT_DIR}/install-1-system.sh" --from-all "$@"
# No se alcanza este punto porque fase 1 ejecuta reboot cuando finaliza

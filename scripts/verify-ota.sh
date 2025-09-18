#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
STATUS=0

log() { printf '[ota] %s\n' "$*"; }
warn() { printf '[ota][WARN] %s\n' "$*"; }
err() { printf '[ota][ERR] %s\n' "$*" >&2; STATUS=1; }

OTA_SCRIPT="$ROOT_DIR/scripts/ota.sh"
if [[ -x "$OTA_SCRIPT" ]]; then
  log 'scripts/ota.sh presente y ejecutable'
else
  err 'scripts/ota.sh ausente o sin permisos'
  exit "$STATUS"
fi

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || echo '')"
if [[ -z "$repo_root" ]]; then
  warn 'Directorio actual no es repositorio git'
else
  log "Repo Git: $repo_root"
  dirty_files="$(git status --porcelain)"
  if [[ -n "$dirty_files" ]]; then
    warn 'Repositorio con cambios locales:'
    printf '%s\n' "$dirty_files"
  else
    log 'Repositorio limpio'
  fi
fi

if "$OTA_SCRIPT" --help >/dev/null 2>&1; then
  log 'scripts/ota.sh responde a --help (dry-run)'
else
  warn 'scripts/ota.sh --help devolvió error'
fi

exit "$STATUS"

#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATUS=0

log() { printf '[installers] %s\n' "$*"; }
warn() { printf '[installers][WARN] %s\n' "$*"; }
err() { printf '[installers][ERR] %s\n' "$*" >&2; STATUS=1; }

mapfile -t INSTALLERS < <(
  find "$ROOT_DIR/scripts" -maxdepth 1 -type f \
    \( -name 'install-*.sh' -o -name 'install-all.sh' -o -name 'install_all.sh' \)
)

if (( ${#INSTALLERS[@]} == 0 )); then
  warn 'No se encontraron instaladores en scripts/'
  exit 0
fi

for script in "${INSTALLERS[@]}"; do
  rel="${script#$ROOT_DIR/}"
  if [[ ! -x "$script" ]]; then
    warn "$rel no es ejecutable"
  fi
  if ! head -n 5 "$script" | grep -q 'set -euo pipefail'; then
    warn "$rel no habilita set -euo pipefail"
  else
    log "$rel declara set -euo pipefail"
  fi
  if ! bash -n "$script"; then
    err "$rel contiene errores de sintaxis"
    continue
  fi
  log "$rel sintaxis OK"
  if grep -Fq '${SCRIPT_DIR}' "$script"; then
    log "$rel usa rutas relativas seguras"
  else
    warn "$rel no usa SCRIPT_DIR/ROOT para rutas; revisar"
  fi
  if grep -q 'sudo reboot' "$script"; then
    warn "$rel contiene reboot automático"
  fi
  if grep -q 'safe_run.sh' "$script"; then
    log "$rel referencia safe_run.sh"
  fi
  log '---'
done

exit "$STATUS"

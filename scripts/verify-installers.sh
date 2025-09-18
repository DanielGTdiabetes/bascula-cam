#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATUS=0

check_flag() {
  local file="$1"
  if ! grep -q 'set -euo pipefail' "$file"; then
    echo "[installers][warn] $file no habilita set -euo pipefail"
  else
    echo "[installers] $file tiene set -euo pipefail"
  fi
}

for script in install-1-system.sh install-2-app.sh; do
  TARGET="$ROOT_DIR/scripts/$script"
  if [[ ! -f "$TARGET" ]]; then
    echo "[installers][err] Falta $TARGET" >&2
    STATUS=1
    continue
  fi
  check_flag "$TARGET"
  if ! bash -n "$TARGET"; then
    echo "[installers][err] $script contiene errores de sintaxis" >&2
    STATUS=1
  else
    echo "[installers] $script sintaxis OK"
  fi
  if [[ ! -x "$TARGET" ]]; then
    echo "[installers][warn] $script no es ejecutable"
  fi
  if grep -q 'sudo reboot' "$TARGET"; then
    echo "[installers][warn] $script fuerza reboot; verificar idempotencia"
  fi
  if grep -q 'rm -rf /' "$TARGET"; then
    echo "[installers][warn] $script contiene rm -rf / (revisar)"
  fi
  if grep -q 'set -euxo pipefail' "$TARGET"; then
    echo "[installers][warn] $script usa set -euxo; revisar para -u opcional"
  fi
  if [[ $script == install-2-app.sh ]]; then
    if ! grep -q 'python3 -m venv' "$TARGET"; then
      echo "[installers][warn] install-2-app.sh no crea entorno virtual explícitamente"
    fi
  fi
  echo "[installers] ---"
done

exit $STATUS

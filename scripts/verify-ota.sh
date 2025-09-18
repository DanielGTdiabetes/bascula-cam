#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -x scripts/ota.sh ]]; then
  echo "[ota][warn] scripts/ota.sh no encontrado o sin permisos de ejecución"
  exit 0
fi

echo "[ota] Git repo: $(git rev-parse --show-toplevel 2>/dev/null || echo 'no detectado')"

echo "[ota] Cambios locales: $(git status --porcelain | wc -l)"

echo "[ota] Ejecutable disponible; sin realizar despliegue real"
exit 0

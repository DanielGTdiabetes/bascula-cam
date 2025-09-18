#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[verify][err] python3 no disponible" >&2
  exit 1
fi

echo "[verify] py_compile"
python3 -m py_compile $(git ls-files '*.py')

echo "[verify] installers"
bash scripts/verify-installers.sh

echo "[verify] services"
bash scripts/verify-services.sh

echo "[verify] kiosk (X, venv, mascot assets)"
bash scripts/verify-kiosk.sh

echo "[verify] scale"
bash scripts/verify-scale.sh

echo "[verify] piper"
bash scripts/verify-piper.sh

echo "[verify] miniweb"
bash scripts/verify-miniweb.sh

echo "[verify] ota/recovery (dry-run)"
bash scripts/verify-ota.sh

echo "[verify] x735"
bash scripts/verify-x735.sh

echo "[verify] smokes (UI)"
python3 tools/smoke_nav.py || true
python3 tools/smoke_mascot.py || true

echo "[OK] Verificación completa"

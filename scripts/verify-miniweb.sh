#!/usr/bin/env bash
set -euo pipefail

if command -v systemctl >/dev/null 2>&1; then
  systemctl --no-pager status bascula-miniweb.service || echo "[miniweb][warn] bascula-miniweb.service no activo"
else
  echo "[miniweb][warn] systemctl no disponible; omitiendo estado de servicio"
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY_BIN="$ROOT/.venv/bin/python"
if [[ ! -x "$PY_BIN" ]]; then
  PY_BIN="python3"
fi

"$PY_BIN" - <<'PY'
import importlib.util
import sys

spec = importlib.util.find_spec('uvicorn')
if spec is None:
    print('[miniweb][err] uvicorn no está instalado')
    sys.exit(1)
print('[miniweb] uvicorn disponible')
PY

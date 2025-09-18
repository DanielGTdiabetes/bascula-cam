#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATUS=0

log() { printf '[miniweb] %s\n' "$*"; }
warn() { printf '[miniweb][WARN] %s\n' "$*"; }
err() { printf '[miniweb][ERR] %s\n' "$*" >&2; STATUS=1; }

PYTHON_BIN="$ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  err "Python no disponible"
  exit "$STATUS"
fi

IMPORT_CHECK=$("$PYTHON_BIN" - <<'PY'
import importlib
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
if str(root) not in sys.path:
    sys.path.insert(0, str(root))

result = {
    "uvicorn": False,
    "app": False,
    "detail": None,
}
try:
    importlib.import_module("uvicorn")
    result["uvicorn"] = True
except Exception as exc:  # pragma: no cover - diagnóstico
    result["detail"] = f"uvicorn: {exc}"

try:
    importlib.import_module("bascula.services.miniweb")
    result["app"] = True
except Exception as exc:  # pragma: no cover - diagnóstico
    if result["detail"]:
        result["detail"] += f"; miniweb: {exc}"
    else:
        result["detail"] = f"miniweb: {exc}"

print(result)
PY
)

if [[ "$IMPORT_CHECK" != *"'app': True"* ]]; then
  err "Fallo importando bascula.services.miniweb: $IMPORT_CHECK"
else
  log 'bascula.services.miniweb importable'
fi

if [[ "$IMPORT_CHECK" != *"'uvicorn': True"* ]]; then
  warn "uvicorn no disponible ($IMPORT_CHECK)"
else
  log 'uvicorn presente'
fi

exit "$STATUS"

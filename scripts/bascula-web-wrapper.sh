#!/usr/bin/env bash
set -euo pipefail
export PYTHONUNBUFFERED=1
VENV=${VENV:-/opt/bascula/current/.venv}
APP=${APP:-/opt/bascula/current}

exec "${VENV}/bin/python" - <<'PY'
import importlib
import os
import pathlib
import sys

app_path = pathlib.Path(os.environ.get("APP", "/opt/bascula/current"))
sys.path.insert(0, str(app_path))

candidates = [
    ("bascula.miniweb", "main"),
    ("bascula.web", "main"),
    ("bascula.app", "main"),
]

for module_name, attr in candidates:
    try:
        module = importlib.import_module(module_name)
        getattr(module, attr)()
        break
    except Exception:
        continue
else:
    raise SystemExit(
        "No web entrypoint found (bascula.miniweb|bascula.web|bascula.app)."
    )
PY

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
    ("bascula.services.wifi_config", "main"),
    ("bascula.web", "main"),
    ("bascula.miniweb", "main"),
    ("bascula.app", "main"),
]

for module_name, attr in candidates:
    try:
        module = importlib.import_module(module_name)
        entrypoint = getattr(module, attr)
    except (ModuleNotFoundError, AttributeError):
        continue
    else:
        entrypoint()
        break
else:
    raise SystemExit(
        "No web entrypoint found (bascula.services.wifi_config|bascula.web|"
        "bascula.miniweb|bascula.app)."
    )
PY

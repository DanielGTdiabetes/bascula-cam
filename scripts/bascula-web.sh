#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="/opt/bascula/current"
VENV="$APP_DIR/.venv"
ENV_FILE="/etc/default/bascula-web"

# Load env file if present
if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  . "$ENV_FILE"
fi

# Defaults
APP_MODULE="${APP_MODULE:-bascula.web.app:app}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8080}"
WORKERS="${WORKERS:-1}"

export PATH="$VENV/bin:$PATH"
export PYTHONUNBUFFERED=1

if [ ! -x "$VENV/bin/python" ]; then
  echo "[err] venv no encontrado en $VENV" >&2
  exit 1
fi

cd "$APP_DIR"

# Sanity checks
"$VENV/bin/python" -c "import importlib; import uvicorn; mod='${APP_MODULE}'.split(':')[0]; importlib.import_module(mod)" || {
  echo "[err] No se pudo importar uvicorn o el módulo APP_MODULE=$APP_MODULE" >&2
  "$VENV/bin/python" -c "import sys, pkgutil, platform; print('python', sys.version); print('platform', platform.platform()); import pkg_resources; print('packages', [d.project_name+':'+d.version for d in pkg_resources.working_set])" || true
  exit 1
}

exec "$VENV/bin/uvicorn" "$APP_MODULE" --host "$HOST" --port "$PORT" --workers "$WORKERS"

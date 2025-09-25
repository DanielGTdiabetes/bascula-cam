#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="/opt/bascula/current"
VENV="$APP_DIR/.venv"
ENV_FILE="/etc/default/bascula-web"

# Defaults (se pueden sobreescribir en /etc/default/bascula-web)
APP_MODULE="${APP_MODULE:-bascula.web.app:app}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8080}"
WORKERS="${WORKERS:-1}"

# Cargar overrides si existen
if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  . "$ENV_FILE"
fi

export PATH="$VENV/bin:$PATH"
export PYTHONUNBUFFERED=1

if [ ! -x "$VENV/bin/python" ]; then
  echo "[err] venv no encontrado en $VENV" >&2
  exit 1
fi

cd "$APP_DIR"

# Sanity check del módulo
"$VENV/bin/python" - <<'PY'
import importlib, os
mod = os.environ.get("APP_MODULE", "bascula.web.app:app").split(":")[0]
importlib.import_module(mod)
PY

exec "$VENV/bin/uvicorn" "$APP_MODULE" --host "$HOST" --port "$PORT" --workers "$WORKERS"

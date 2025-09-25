#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="/opt/bascula/current"
VENV="$APP_DIR/.venv"
ENV_FILE="/etc/default/bascula-web"

APP_MODULE="${APP_MODULE:-bascula.web.app:app}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8080}"
WORKERS="${WORKERS:-1}"

if [ -f "$ENV_FILE" ]; then
  while IFS= read -r raw_line; do
    line="${raw_line%%#*}"
    line="${line#${line%%[![:space:]]*}}"
    line="${line%${line##*[![:space:]]}}"
    [ -z "$line" ] && continue
    case "$line" in
      *"="*) : ;;
      *) continue ;;
    esac
    key="${line%%=*}"
    value="${line#*=}"
    key="${key%${key##*[![:space:]]}}"
    value="${value#${value%%[![:space:]]*}}"
    value="${value%${value##*[![:space:]]}}"
    [[ $key =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    case "$value" in
      *'$('*|*'`'*|*'${'*|*';'*|*'&'*|*'|'*|*'<'*|*'>'* ) continue ;;
    esac
    export "$key=$value"
  done < "$ENV_FILE"
fi

export PATH="$VENV/bin:$PATH"
export PYTHONUNBUFFERED=1

if [ ! -x "$VENV/bin/python" ]; then
  echo "[err] venv no encontrado en $VENV" >&2
  exit 1
fi

cd "$APP_DIR"

"$VENV/bin/python" - <<'PY'
import importlib
import os

module_name = os.environ.get("APP_MODULE", "bascula.web.app:app").split(":", 1)[0]
importlib.import_module(module_name)
PY

exec "$VENV/bin/uvicorn" "$APP_MODULE" --host "$HOST" --port "$PORT" --workers "$WORKERS"

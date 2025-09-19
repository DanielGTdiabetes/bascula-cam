#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/pi/bascula-cam"
cd "$ROOT"
PY="$ROOT/.venv/bin/python"
PORT="${BASCULA_MINIWEB_PORT:-8080}"
if ss -tulpen | grep -q ":$PORT "; then PORT=8078; fi
exec "$PY" -m uvicorn bascula.services.miniweb:app --host 0.0.0.0 --port "$PORT"

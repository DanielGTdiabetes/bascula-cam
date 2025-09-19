#!/usr/bin/env bash
set -euo pipefail
ROOT="/home/pi/bascula-cam"
VENV="$ROOT/.venv/bin/python"
cd "$ROOT"
PORT=8080
if ss -tulpen | grep -q ":$PORT "; then PORT=8078; fi
exec "$VENV" -m uvicorn bascula.services.miniweb:app --host 0.0.0.0 --port "$PORT"

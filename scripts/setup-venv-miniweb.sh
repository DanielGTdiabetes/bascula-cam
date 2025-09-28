#!/usr/bin/env bash
set -euo pipefail
VENV="/opt/bascula/current/.venv"
sudo apt-get update
sudo apt-get install -y python3-venv python3-full
[ -d "$VENV" ] || { python3 -m venv "$VENV"; sudo chown -R pi:pi "$VENV"; }
"$VENV/bin/pip" install --upgrade pip
"$VENV/bin/pip" install "uvicorn>=0.29,<0.33" "fastapi>=0.114,<0.120" "python-dotenv>=1.0" "jinja2>=3.1" "itsdangerous>=2.1"
echo "[ok] venv listo en $VENV"

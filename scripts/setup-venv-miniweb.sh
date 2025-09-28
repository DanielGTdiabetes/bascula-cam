#!/usr/bin/env bash
set -euo pipefail
VENV="/opt/bascula/current/.venv"

sudo apt-get update
sudo apt-get install -y python3-venv python3-full

sudo install -d -m 0755 -o pi -g pi "$VENV"
sudo -u pi python3 -m venv "$VENV"

sudo -u pi "$VENV/bin/pip" install --upgrade pip
sudo -u pi "$VENV/bin/pip" install \
    "uvicorn>=0.29,<0.33" \
    "fastapi>=0.114,<0.120" \
    "python-dotenv>=1.0" \
    "jinja2>=3.1" \
    "itsdangerous>=2.1"
echo "[ok] venv listo en $VENV"

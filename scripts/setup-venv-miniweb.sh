#!/usr/bin/env bash
set -euo pipefail
VENV=/opt/bascula/venv
sudo apt-get update
sudo apt-get install -y python3-venv python3-full
if [ ! -d "$VENV" ]; then
  sudo python3 -m venv "$VENV"
  sudo chown -R pi:pi "$VENV"
fi
"$VENV/bin/pip" install --upgrade pip
"$VENV/bin/pip" install "uvicorn>=0.29,<0.33" "fastapi>=0.114,<0.120"

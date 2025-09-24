#!/usr/bin/env bash
set -euo pipefail

export HOME="/home/pi"
export USER="pi"
export XDG_RUNTIME_DIR="/run/user/1000"
export DISPLAY=":0"

if [[ ${EUID:-0} -eq 0 ]]; then
  echo "bascula-app: no debe ejecutarse como root" >&2
  exit 1
fi

APP="${APP:-/opt/bascula/current}"
SCRIPT="${APP}/scripts/run-ui.sh"
if [[ ! -x "${SCRIPT}" ]]; then
  echo "bascula-app: no se encontró ${SCRIPT}" >&2
  exit 1
fi

exec "${SCRIPT}"

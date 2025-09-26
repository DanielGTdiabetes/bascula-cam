#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID:-0} -eq 0 ]]; then
  echo "bascula-app: no debe ejecutarse como root" >&2
  exit 1
fi

: "${DISPLAY:=:0}"
: "${USER:=pi}"
: "${LOGNAME:=${USER}}"
: "${HOME:=/home/${USER}}"
export DISPLAY USER LOGNAME HOME

exec /usr/bin/startx -- -keeptty -logfile /var/log/bascula/xorg.log >>/var/log/bascula/app.log 2>&1

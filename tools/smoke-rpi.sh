#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

APP_VENV="${APP_VENV:-/opt/bascula/current/.venv}"
APP_PY="${APP_VENV}/bin/python"

if [[ ! -x "${APP_PY}" ]]; then
  echo "[ERR] No se encontró el intérprete en ${APP_PY}" >&2
  exit 1
fi

export PYTHONNOUSERSITE=1

echo "[smoke] Verificando imports clave en ${APP_VENV}"
"${APP_PY}" - <<'PY'
import sys
import numpy
import cv2
import simplejpeg
from picamera2 import Picamera2
import tkinter

print("PY", sys.version.split()[0], "NumPy", numpy.__version__, "cv2", cv2.__version__)
print("simplejpeg", simplejpeg.__file__)
print("Picamera2 OK", Picamera2)
print("Tk", tkinter.TkVersion)
PY

TMP_IMG="/tmp/bascula-smoke-rpi.jpg"
echo "[smoke] Ejecutando libcamera-still"
if command -v libcamera-still >/dev/null; then
  if libcamera-still -n -o "${TMP_IMG}" && [ -s "${TMP_IMG}" ]; then
    echo "[smoke] libcamera OK (${TMP_IMG})"
  else
    echo "[WARN] libcamera-still no generó imagen" >&2
  fi
else
  echo "[WARN] libcamera-still no está instalado" >&2
fi
rm -f "${TMP_IMG}" 2>/dev/null || true

have_systemd() {
  command -v systemctl >/dev/null 2>&1 && [[ -d /run/systemd/system ]]
}

echo "[smoke] Estado de servicios"
if have_systemd; then
  systemctl --no-pager --plain --failed || true
  for svc in bascula-ui bascula-miniweb ocr-service; do
    if systemctl list-units --type=service --all | grep -q "${svc}.service"; then
      if systemctl is-active --quiet "${svc}.service"; then
        echo "[smoke] ${svc}.service: active"
      else
        systemctl status "${svc}.service" --no-pager || true
      fi
    else
      echo "[INFO] ${svc}.service no está definido"
    fi
  done
else
  echo "[INFO] systemd no disponible"
fi

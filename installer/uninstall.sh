#!/usr/bin/env bash
set -euo pipefail
# -------------------------------------------------------------
# SMART BÁSCULA CAM - uninstall.sh
# Detiene y deshabilita el servicio; NO borra el proyecto.
# Uso:
#   bash uninstall.sh
# -------------------------------------------------------------

SVC="bascula-cam.service"
UNIT="$HOME/.config/systemd/user/$SVC"

echo "==> Deteniendo servicio (si existe)..."
systemctl --user stop "$SVC" || true
systemctl --user disable "$SVC" || true
systemctl --user daemon-reload || true

if [[ -f "$UNIT" ]]; then
  rm -f "$UNIT"
  echo "==> Eliminado: $UNIT"
else
  echo "Aviso: $UNIT no existe."
fi

echo "==> Hecho."

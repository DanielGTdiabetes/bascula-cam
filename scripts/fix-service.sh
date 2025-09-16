#!/usr/bin/env bash
set -euo pipefail

# Script para arreglar el servicio bascula-ui con las rutas correctas

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  echo "Este script debe ejecutarse con sudo o como root"
  exit 1
fi

echo "Deteniendo servicio bascula-ui..."
systemctl stop bascula-ui.service || true

echo "Deshabilitando servicio bascula-ui..."
systemctl disable bascula-ui.service || true

echo "Copiando archivo de servicio actualizado..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
SERVICE_SRC="${REPO_ROOT}/systemd/bascula-ui.service"
SERVICE_DST="/etc/systemd/system/bascula-ui.service"

if [[ ! -f "${SERVICE_SRC}" ]]; then
  echo "ERROR: No se encontró ${SERVICE_SRC}"
  exit 1
fi

cp "${SERVICE_SRC}" "${SERVICE_DST}"
echo "Servicio copiado a ${SERVICE_DST}"

echo "Recargando daemon de systemd..."
systemctl daemon-reload

echo "Habilitando servicio bascula-ui..."
systemctl enable bascula-ui.service

echo "Iniciando servicio bascula-ui..."
systemctl start bascula-ui.service

sleep 3

echo "Verificando estado del servicio..."
if systemctl is-active --quiet bascula-ui.service; then
  echo "✓ bascula-ui.service está activo"
  systemctl status bascula-ui.service --no-pager -l
else
  echo "✗ bascula-ui.service falló al iniciar"
  echo "Logs del servicio:"
  journalctl -u bascula-ui.service -n 20 --no-pager
  exit 1
fi

echo "Servicio arreglado exitosamente"

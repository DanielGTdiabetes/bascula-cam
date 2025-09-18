#!/usr/bin/env bash
set -euo pipefail

echo "[inst] Grupos de pi:"; id pi || true
echo "[inst] Dispositivos típicos:"; ls -l /dev/ttyACM* /dev/ttyUSB* /dev/i2c* 2>/dev/null || true
echo "[inst] Udev rules (scale):"; grep -H . /etc/udev/rules.d/99-scale.rules 2>/dev/null || echo "(no rules)"
echo "[inst] Variable BASCULA_DEVICE: ${BASCULA_DEVICE:-<vacía>}"
/home/pi/bascula-cam/.venv/bin/python /home/pi/bascula-cam/tools/check_scale.py || true


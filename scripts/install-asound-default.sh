#!/usr/bin/env bash
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Este script debe ejecutarse con sudo (root)" >&2
  exit 1
fi

CARD=${1:-MAX98357A}
DEVNUM=${2:-0}
CONF=/etc/asound.conf

echo "Configurando ALSA default -> plughw:${CARD},${DEVNUM} en ${CONF}"
tee "$CONF" >/dev/null <<EOF
pcm.!default {
  type plug
  slave.pcm "plughw:${CARD},${DEVNUM}"
}
ctl.!default {
  type hw
  card "${CARD}"
}
EOF

echo "Hecho. Puedes probar con: aplay -L && speaker-test -c1 -D plughw:${CARD},${DEVNUM} -t sine -f 1000 -l 1"
echo "Reinicia para aplicar a todos los servicios: sudo reboot"


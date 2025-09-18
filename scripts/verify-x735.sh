#!/usr/bin/env bash
set -euo pipefail

if command -v systemctl >/dev/null 2>&1; then
  systemctl --no-pager status x735-fan.service || echo "[x735][warn] x735-fan.service no activo"
else
  echo "[x735][warn] systemctl no disponible; omitiendo estado del servicio"
fi

if [[ -x /usr/local/bin/x735.sh ]]; then
  echo "[x735] Script de control x735 presente"
else
  echo "[x735][warn] /usr/local/bin/x735.sh no encontrado o sin permisos"
fi

exit 0

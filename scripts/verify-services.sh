#!/usr/bin/env bash
set -euo pipefail

if ! command -v systemctl >/dev/null 2>&1; then
  echo "[services][warn] systemctl no disponible; omitiendo comprobaciones de unidades"
else
  sc() {
    systemctl --no-pager "$@"
  }

  echo "[services] bascula-ui.service"
  sc cat bascula-ui.service 2>/dev/null | sed -n '1,120p' || echo "[services][warn] No se pudo leer bascula-ui.service"
  sc status bascula-ui.service || echo "[services][warn] bascula-ui.service no activo"

  echo "[services] bascula-recovery.service"
  sc status bascula-recovery.service || echo "[services][warn] bascula-recovery.service no activo"

  echo "[services] bascula-miniweb.service"
  sc status bascula-miniweb.service || echo "[services][warn] bascula-miniweb.service no activo"

  env_dump="$(sc show-environment 2>/dev/null || true)"
  if ! printf '%s' "$env_dump" | grep -q 'DISPLAY='; then
    echo "[services][warn] DISPLAY no exportado en la sesión systemd"
  fi
  if ! printf '%s' "$env_dump" | grep -q 'XAUTHORITY='; then
    echo "[services][warn] XAUTHORITY no definido en la sesión systemd"
  fi
fi

XINIT="$HOME/.xinitrc"
if [[ -f "$XINIT" ]]; then
  if grep -q 'safe_run.sh' "$XINIT"; then
    echo "[services] ~/.xinitrc invoca safe_run.sh"
  else
    echo "[services][warn] ~/.xinitrc no invoca scripts/safe_run.sh"
  fi
else
  echo "[services][warn] ~/.xinitrc ausente"
fi

exit 0

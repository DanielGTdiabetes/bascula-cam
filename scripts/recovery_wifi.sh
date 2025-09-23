#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="/opt/bascula/current/scripts"
NET_FALLBACK="${SCRIPT_DIR}/net-fallback.sh"
SSID="${RECOVERY_SSID:-Bascula_AP}"
PASS="${RECOVERY_PASS:-bascula1234}"
PORT=${BASCULA_MINIWEB_PORT:-${BASCULA_WEB_PORT:-8080}}

log() { printf '[recovery-wifi] %s\n' "$*"; }

if [[ -x "$NET_FALLBACK" ]]; then
  log "Activando punto de acceso de respaldo"
  "$NET_FALLBACK" || true
fi

get_ips() {
  local iface output
  if command -v nmcli >/dev/null 2>&1; then
    for iface in $(nmcli -t -f DEVICE,STATE dev | awk -F: '$2=="connected"{print $1}'); do
      nmcli -g IP4.ADDRESS dev show "$iface" 2>/dev/null | sed 's#/.*##'
    done
  fi
  hostname -I 2>/dev/null | tr -s ' '
}

IPS=$(get_ips | tr ' ' '\n' | grep -E '^[0-9]' | sort -u)

cat <<EOF
=== Configuración Wi-Fi de emergencia ===
SSID:    ${SSID}
Clave:   ${PASS}

IPs disponibles:
EOF

if [[ -z "$IPS" ]]; then
  echo "  (sin dirección asignada)"
else
  while read -r ip; do
    [[ -z "$ip" ]] && continue
    printf '  %s\n' "$ip"
  done <<<"$IPS"
fi

cat <<EOF

Mini-web: http://<IP>:$PORT
Conéctate al punto de acceso y abre el enlace para configurar la báscula.
EOF

#!/usr/bin/env bash
set -euo pipefail

is_connected() {
  local type="$1"
  nmcli -t -f DEVICE,TYPE,STATE dev | awk -F: -v t="${type}" '$2==t && $3=="connected"{ok=1} END{exit ok?0:1}'
}

ap_up() {
  if ! nmcli -t -f NAME,TYPE con show --active | awk -F: '$1=="BasculaAP" && $2=="wifi"{ok=1} END{exit ok?0:1}'; then
    nmcli radio wifi on || true
    rfkill unblock wifi || true
    IFACE="$(nmcli -t -f DEVICE,TYPE dev | awk -F: '$2=="wifi"{print $1; exit}')"
    nmcli con up "BasculaAP" ifname "${IFACE}" || nmcli con up "BasculaAP" || true
  fi
}

ap_down() {
  if nmcli -t -f NAME,TYPE con show --active | awk -F: '$1=="BasculaAP" && $2=="wifi"{ok=1} END{exit ok?0:1}'; then
    nmcli con down "BasculaAP" || true
  fi
}

main() {
  # Perfil AP si falta (idempotente)
  if ! nmcli -t -f NAME con show | grep -Fxq "BasculaAP"; then
    IFACE="$(nmcli -t -f DEVICE,TYPE dev | awk -F: '$2=="wifi"{print $1; exit}')"
    nmcli con add type wifi ifname "${IFACE}" con-name "BasculaAP" ssid "Bascula_AP" \
      802-11-wireless.mode ap 802-11-wireless.band bg 802-11-wireless.channel 6 \
      ipv4.method shared ipv6.method ignore \
      wifi-sec.key-mgmt wpa-psk wifi-sec.psk "bascula1234" || true
  fi

  if is_connected "ethernet"; then ap_down; exit 0; fi
  if is_connected "wifi";     then ap_down; exit 0; fi
  ap_up
}
main "$@"

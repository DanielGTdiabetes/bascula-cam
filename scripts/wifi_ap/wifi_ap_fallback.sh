#!/usr/bin/env bash
# scripts/wifi_ap/wifi_ap_fallback.sh — levanta un AP si no hay Internet
set -euo pipefail

SSID="${SSID:-BasculaCam-Setup}"
PASS="${PASS:-bascula1234}"
IFACE="${IFACE:-wlan0}"
DNSMASQ_CONF="/etc/dnsmasq.d/bascula-ap.conf"
HOSTAPD_CONF="/etc/hostapd/hostapd.conf"

log() { echo "[wifi-ap] $*"; }

check_internet() {
  ping -c1 -W2 8.8.8.8 >/dev/null 2>&1
}

# Si ya hay Internet, no hacemos nada
if check_internet; then
  log "Internet detectado, no es necesario AP."
  exit 0
fi

log "No se detecta internet. Configurando AP en ${IFACE}..."

# IP estática para el AP
ip link set "${IFACE}" down || true
ip addr flush dev "${IFACE}" || true
ip addr add 192.168.50.1/24 dev "${IFACE}"
ip link set "${IFACE}" up

# dnsmasq (DHCP + DNS local)
cat > "${DNSMASQ_CONF}" <<EOF
interface=${IFACE}
dhcp-range=192.168.50.10,192.168.50.100,12h
address=/#/192.168.50.1
EOF

# hostapd
cat > "${HOSTAPD_CONF}" <<EOF
interface=${IFACE}
ssid=${SSID}
hw_mode=g
channel=6
auth_algs=1
wmm_enabled=0
wpa=2
wpa_passphrase=${PASS}
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
EOF

systemctl stop dnsmasq || true
systemctl stop hostapd || true
systemctl start dnsmasq
systemctl start hostapd

log "AP levantado con SSID=${SSID}, PASS=${PASS} en ${IFACE}"
log "Conéctate y abre: http://192.168.50.1"

#!/usr/bin/env bash
set -euo pipefail

# Detecta interfaz Wi-Fi gestionada por NetworkManager (primera)
WIFI_IF="${WIFI_IF:-$(nmcli -t -f DEVICE,TYPE dev | awk -F: '$2=="wifi"{print $1;exit}')}"

if [[ -z "${WIFI_IF}" ]]; then
  echo "[setup_ap_nm] ERROR: no se detectó interfaz Wi-Fi gestionada por NetworkManager" >&2
  exit 1
fi

SSID="${SSID:-Bascula_AP}"
PSK="${PSK:-bascula1234}"
AP_CON="${AP_CON:-BasculaAP}"
AP_ADDR="${AP_ADDR:-10.42.0.1/24}"
AP_CHANNEL="${AP_CHANNEL:-6}"
COUNTRY="${WIFI_COUNTRY:-ES}"

echo "[setup_ap_nm] Wi-Fi IF=${WIFI_IF} SSID=${SSID} CON=${AP_CON}"

# 1) País Wi-Fi / regulatory domain
if command -v raspi-config >/dev/null 2>&1; then
  sudo raspi-config nonint do_wifi_country "${COUNTRY}" || true
fi
sudo iw reg set "${COUNTRY}" || true

# 2) AP soportada
if command -v iw >/dev/null 2>&1; then
  if ! iw list | awk '/Supported interface modes/{flag=1;next}/^$/{flag=0}flag' | grep -q '\bAP\b'; then
    echo "[setup_ap_nm] ADVERTENCIA: el driver no reporta modo AP; se intenta igualmente." >&2
  fi
fi

# 3) Evita conflictos con servicios externos
sudo systemctl stop hostapd dnsmasq 2>/dev/null || true

# 4) Crea o normaliza la conexión AP
if nmcli -t -f NAME con show | grep -Fxq "${AP_CON}"; then
  sudo nmcli con mod "${AP_CON}" connection.interface-name "${WIFI_IF}" || true
else
  sudo nmcli con add type wifi ifname "${WIFI_IF}" con-name "${AP_CON}" ssid "${SSID}"
fi

# Parámetros AP + WPA2/AES
sudo nmcli con mod "${AP_CON}" \
  connection.id "${AP_CON}" \
  connection.interface-name "${WIFI_IF}" \
  802-11-wireless.mode ap \
  802-11-wireless.band bg \
  802-11-wireless.channel "${AP_CHANNEL}" \
  802-11-wireless.ssid "${SSID}" \
  wifi-sec.key-mgmt wpa-psk \
  wifi-sec.psk "${PSK}" \
  802-11-wireless-security.proto rsn \
  802-11-wireless-security.group ccmp \
  802-11-wireless-security.pairwise ccmp

# NAT + DHCP embebido de NM
sudo nmcli con mod "${AP_CON}" \
  ipv4.method shared \
  ipv4.addresses "${AP_ADDR}" \
  ipv6.method ignore \
  connection.autoconnect no \
  connection.autoconnect-priority 0 \
  connection.autoconnect-retries 0

# 5) Desactiva Wi-Fi cliente por defecto que compite (si existe)
if nmcli -t -f NAME,TYPE con show | awk -F: '$2=="wifi"{print $1}' | grep -Fxq "preconfigured"; then
  sudo nmcli con mod preconfigured connection.autoconnect no || true
fi

# 6) Levanta la AP
sudo nmcli radio wifi on
sudo rfkill unblock wifi 2>/dev/null || true
sudo ip link set "${WIFI_IF}" up || true
sudo nmcli con up "${AP_CON}" ifname "${WIFI_IF}"

# 7) Verificación rápida
sleep 1
IFADDR=$(ip -4 -o addr show dev "${WIFI_IF}" | awk '{print $4}' | head -n1 || true)
echo "[setup_ap_nm] ${WIFI_IF} addr=${IFADDR}"
if [[ "${IFADDR}" != 10.42.0.1/24 ]]; then
  echo "[setup_ap_nm] ADVERTENCIA: no se ve 10.42.0.1/24 aún (IF=${WIFI_IF}); revisar NetworkManager logs." >&2
fi

echo "[setup_ap_nm] OK"

#!/usr/bin/env bash
set -euo pipefail
AP_CON="${AP_CON:-BasculaAP}"
nmcli -t -f NAME con show | grep -Fxq "${AP_CON}" || { echo "[verify-ap] Falta conexión ${AP_CON}"; exit 2; }
nmcli -t -f all con show "${AP_CON}" | grep -q '^ipv4.method:.*shared' || { echo "[verify-ap] Falta ipv4.method=shared"; exit 2; }
nmcli -t -f all con show "${AP_CON}" | grep -q '^wifi-sec.key-mgmt:.*wpa-psk' || { echo "[verify-ap] Falta wpa-psk"; exit 2; }
echo "[verify-ap] OK"

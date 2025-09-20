#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  TARGET_USER="${TARGET_USER:-${SUDO_USER:-pi}}"
  exec sudo TARGET_USER="${TARGET_USER}" bash "$0" "$@"
fi

TARGET_USER="${TARGET_USER:-${SUDO_USER:-pi}}"

free_tcp_port() {
  local port="$1"
  if command -v ss >/dev/null 2>&1 && ss -ltn "sport = :${port}" | grep -q LISTEN; then
    echo "[inst] Freeing tcp:${port}"
    if command -v fuser >/dev/null 2>&1; then
      fuser -k "${port}"/tcp >/dev/null 2>&1 || true
    fi
    sleep 0.5
    return
  fi
  if command -v fuser >/dev/null 2>&1 && fuser "${port}"/tcp >/dev/null 2>&1; then
    echo "[inst] Freeing tcp:${port}"
    fuser -k "${port}"/tcp >/dev/null 2>&1 || true
    sleep 0.5
  fi
}

nm_up_ap() {
  local _opts=$-
  set +e
  if ! command -v nmcli >/dev/null 2>&1; then
    echo "[ap] nmcli no disponible; omitiendo Hotspot (ok)"
    [[ $_opts == *e* ]] && set -e
    return 0
  fi
  if ! ip link show wlan0 >/dev/null 2>&1; then
    echo "[ap] wlan0 no disponible; omitiendo Hotspot (ok)"
    [[ $_opts == *e* ]] && set -e
    return 0
  fi
  if nmcli -t -f DEVICE,TYPE,STATE,CONNECTION dev | grep -q '^wlan0:wifi:connected:'; then
    echo "[ap] wlan0 está conectado como cliente; no se levanta AP (ok)"
    [[ $_opts == *e* ]] && set -e
    return 0
  fi
  if nmcli -t -f NAME con show | grep -qx "BasculaAP"; then
    echo "[ap] Conexión BasculaAP ya existe"
  else
    echo "[ap] Creando BasculaAP…"
    nmcli con add type wifi ifname wlan0 con-name BasculaAP ssid "Bascula_AP" \
      802-11-wireless.mode ap 802-11-wireless.band bg 802-11-wireless.channel 6 \
      ipv4.method shared ipv6.method ignore \
      802-11-wireless-security.key-mgmt wpa-psk 802-11-wireless-security.psk "bascula1234" \
      || echo "[ap] Aviso: nmcli con add BasculaAP devolvió error; se continúa"
  fi
  echo "[ap] Activando BasculaAP (best-effort)…"
  nmcli con up BasculaAP ifname wlan0 || echo "[ap] Aviso: nmcli con up BasculaAP devolvió error; se continúa"
  [[ $_opts == *e* ]] && set -e
}

PHASE=2 TARGET_USER="${TARGET_USER}" bash "${SCRIPT_DIR}/install-all.sh" "$@"

install -d -m 0755 /etc/bascula
install -D -m 0644 "${ROOT_DIR}/systemd/bascula-web.env" /etc/default/bascula-web
install -D -m 0644 /dev/null /etc/bascula/WEB_READY
install -D -m 0644 /dev/null /etc/bascula/APP_READY

nm_up_ap

install -D -m 0644 "${ROOT_DIR}/systemd/bascula-web.service" /etc/systemd/system/bascula-web.service
install -D -m 0644 "${ROOT_DIR}/systemd/bascula-app.service" /etc/systemd/system/bascula-app.service
systemctl daemon-reload

for svc in bascula-web.service bascula-app.service; do
  systemctl stop "${svc}" 2>/dev/null || true
  systemctl reset-failed "${svc}" 2>/dev/null || true
done

PORT="$(. /etc/default/bascula-web; printf '%s' \"${BASCULA_WEB_PORT:-8078}\")"
free_tcp_port "${PORT}"

systemctl enable bascula-web.service
systemctl enable bascula-app.service

systemctl start bascula-web.service
systemctl restart bascula-app.service

health_ok=""
for i in $(seq 1 15); do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null; then
    echo "[verify] Mini-web: OK"
    health_ok=1
    break
  fi
  sleep 1
done

if [[ -z "${health_ok}" ]]; then
  echo "[ERR ] Mini-web: health endpoint did not respond on 127.0.0.1:${PORT}"
  echo "------ journald tail (bascula-web) ------"
  journalctl -u bascula-web.service -n 80 --no-pager || true
  exit 1
fi

echo "[install-2-app] Servicios bascula-web y bascula-app activos"

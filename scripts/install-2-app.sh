#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  TARGET_USER="${TARGET_USER:-${SUDO_USER:-pi}}"
  exec sudo TARGET_USER="${TARGET_USER}" bash "$0" "$@"
fi

TARGET_USER="${TARGET_USER:-${SUDO_USER:-pi}}"

install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_USER}" "/home/${TARGET_USER}/.config/bascula"

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

apt-get install -y xserver-xorg x11-xserver-utils xinit xserver-xorg-legacy unclutter

install -D -m 0644 /dev/null /etc/Xwrapper.config
cat >/etc/Xwrapper.config <<'EOF'
allowed_users=anybody
needs_root_rights=yes
EOF

usermod -aG video,render,input pi || true
loginctl enable-linger pi || true
install -d -o pi -g pi -m 0700 /run/user/1000 || true
install -d -m 1777 /tmp/.X11-unix || true
install -D -m 0644 "${ROOT_DIR}/packaging/tmpfiles/bascula-x11.conf" /etc/tmpfiles.d/bascula-x11.conf
systemd-tmpfiles --create /etc/tmpfiles.d/bascula-x11.conf || true

install -d -m 0755 /etc/bascula
{
  BASCULA_USER=pi
  BASCULA_GROUP=pi
  BASCULA_PREFIX=/opt/bascula/current
  BASCULA_VENV="${BASCULA_VENV:-/opt/bascula/current/.venv}"
  BASCULA_CFG_DIR=/home/pi/.config/bascula
  BASCULA_RUNTIME_DIR=/run/bascula
  BASCULA_WEB_HOST=0.0.0.0
  BASCULA_WEB_PORT=${BASCULA_WEB_PORT:-8080}
  BASCULA_MINIWEB_PORT=${BASCULA_MINIWEB_PORT:-8080}
  FLASK_RUN_HOST=${FLASK_RUN_HOST:-0.0.0.0}

  # Fallback dev (no OTA instalado)
  if [[ ! -x "${BASCULA_VENV}/bin/python" && -x "/home/pi/bascula-cam/.venv/bin/python" ]]; then
    echo "[inst] OTA venv no encontrado; usando fallback de desarrollo"
    BASCULA_PREFIX=/home/pi/bascula-cam
    BASCULA_VENV=/home/pi/bascula-cam/.venv
  fi

  cat <<EOF
BASCULA_USER=${BASCULA_USER}
BASCULA_GROUP=${BASCULA_GROUP}
BASCULA_PREFIX=${BASCULA_PREFIX}
BASCULA_VENV=${BASCULA_VENV}
BASCULA_CFG_DIR=${BASCULA_CFG_DIR}
BASCULA_RUNTIME_DIR=${BASCULA_RUNTIME_DIR}
BASCULA_WEB_HOST=${BASCULA_WEB_HOST}
BASCULA_WEB_PORT=${BASCULA_WEB_PORT}
BASCULA_MINIWEB_PORT=${BASCULA_MINIWEB_PORT}
FLASK_RUN_HOST=${FLASK_RUN_HOST}
EOF
} | tee /etc/default/bascula >/dev/null
install -D -m 0644 /dev/null /etc/bascula/WEB_READY
install -D -m 0644 /dev/null /etc/bascula/APP_READY

nm_up_ap

install -D -m 0644 "${ROOT_DIR}/systemd/bascula-web.service" /etc/systemd/system/bascula-web.service
install -D -m 0644 "${ROOT_DIR}/systemd/bascula-app.service" /etc/systemd/system/bascula-app.service
install -D -m 0644 "${ROOT_DIR}/systemd/bascula-web.service.d/10-writable-home.conf" \
  /etc/systemd/system/bascula-web.service.d/10-writable-home.conf
install -D -m 0644 "${ROOT_DIR}/systemd/bascula-web.service.d/20-env-and-exec.conf" \
  /etc/systemd/system/bascula-web.service.d/20-env-and-exec.conf
install -D -m 0755 "${ROOT_DIR}/scripts/xsession.sh" /opt/bascula/current/scripts/xsession.sh

for svc in bascula-web.service bascula-app.service; do
  systemctl stop "${svc}" 2>/dev/null || true
  systemctl reset-failed "${svc}" 2>/dev/null || true
done

. /etc/default/bascula
# Puerto de mini-web (compatibilidad hacia atrás):
# 1) BASCULA_MINIWEB_PORT (histórico)  2) BASCULA_WEB_PORT  3) 8080 por defecto
PORT="${BASCULA_MINIWEB_PORT:-${BASCULA_WEB_PORT:-8080}}"
free_tcp_port "${PORT}"

systemctl disable getty@tty1.service || true

systemctl daemon-reload
systemctl enable --now bascula-app.service || true

# Si el puerto ya está ocupado, avisamos y no intentamos arrancar otra instancia;
# el health-check comprobará este mismo puerto.
if ss -ltnp | grep -qE ":${PORT}\\b"; then
  echo "[WARN] Port ${PORT} is already in use. Skipping start. Health check will probe the running service."
else
  systemctl enable --now bascula-web.service
fi

health_ok=""
delay=1
for i in $(seq 1 8); do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null; then
    echo "[verify] Mini-web: OK"
    health_ok=1
    break
  fi
  sleep "${delay}"
  delay=$((delay * 2))
  if (( delay > 8 )); then
    delay=8
  fi
done

if [[ -z "${health_ok}" ]]; then
  echo "[ERR ] Mini-web: health endpoint did not respond on 127.0.0.1:${PORT}"
  echo "------ journald tail (bascula-web) ------"
  journalctl -u bascula-web.service -n 80 --no-pager || true
  exit 1
fi

if ! curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null; then
  journalctl -u bascula-web.service -n 120 --no-pager || true
  exit 1
fi

echo "[install-2-app] Servicios bascula-web y bascula-app activos"
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo "Mini-web: http://${IP:-<IP>}:${PORT}/"

sleep 3
if ! systemctl is-active --quiet bascula-app.service; then
  journalctl -u bascula-app -n 200 --no-pager || true
  tail -n 120 "/home/pi/.local/share/xorg/Xorg.0.log" || true
  echo "[ERR] bascula-app no ha arrancado; revisa logs anteriores" >&2
  exit 1
fi

pgrep -af "Xorg|startx" || { echo "[ERR] Xorg no está corriendo"; exit 1; }
pgrep -af "python .*bascula.ui.app" || { echo "[ERR] UI de bascula no detectada"; exit 1; }

echo "[OK] UI arrancada correctamente con startx + systemd"

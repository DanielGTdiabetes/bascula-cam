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

PHASE=2 TARGET_USER="${TARGET_USER}" bash "${SCRIPT_DIR}/install-all.sh" "$@"

apt-get install -y xserver-xorg x11-xserver-utils xinit xserver-xorg-legacy unclutter \
                   libcamera-apps v4l-utils python3-picamera2

install -D -m 0644 /dev/null /etc/Xwrapper.config
cat >/etc/Xwrapper.config <<'EOF'
allowed_users=anybody
needs_root_rights=yes
EOF

usermod -aG video,render,input pi || true
loginctl enable-linger pi || true
install -D -m 0644 "${ROOT_DIR}/packaging/tmpfiles/bascula-x11.conf" /etc/tmpfiles.d/bascula-x11.conf
systemd-tmpfiles --create /etc/tmpfiles.d/bascula-x11.conf || true

install -d -m 0755 -o pi -g pi /etc/bascula
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

install -D -m 0644 "${ROOT_DIR}/systemd/bascula-web.service" /etc/systemd/system/bascula-web.service
install -D -m 0644 "${ROOT_DIR}/systemd/bascula-app.service" /etc/systemd/system/bascula-app.service
install -D -m 0644 "${ROOT_DIR}/systemd/bascula-web.service.d/10-writable-home.conf" \
  /etc/systemd/system/bascula-web.service.d/10-writable-home.conf
install -D -m 0644 "${ROOT_DIR}/systemd/bascula-web.service.d/20-env-and-exec.conf" \
  /etc/systemd/system/bascula-web.service.d/20-env-and-exec.conf
install -D -m 0755 "${ROOT_DIR}/scripts/xsession.sh" /opt/bascula/current/scripts/xsession.sh
install -D -m 0755 "${ROOT_DIR}/scripts/net-fallback.sh" /opt/bascula/current/scripts/net-fallback.sh
install -D -m 0644 "${ROOT_DIR}/systemd/bascula-net-fallback.service" /etc/systemd/system/bascula-net-fallback.service

for svc in bascula-web.service bascula-app.service; do
  systemctl stop "${svc}" 2>/dev/null || true
  systemctl reset-failed "${svc}" 2>/dev/null || true
done

. /etc/default/bascula
# Puerto de mini-web (compatibilidad hacia atrás):
# 1) BASCULA_MINIWEB_PORT (histórico)  2) BASCULA_WEB_PORT  3) 8080 por defecto
PORT="${BASCULA_MINIWEB_PORT:-${BASCULA_WEB_PORT:-8080}}"

if ss -ltn "( sport = :${PORT} )" | grep -q ":${PORT}"; then
  echo "[WARN] Port ${PORT} is already in use. bascula-web may fail to start."
fi

systemctl disable getty@tty1.service || true

systemctl daemon-reload
systemctl enable --now bascula-app.service || true
systemctl enable --now bascula-web.service || true
systemctl enable --now bascula-net-fallback.service || true

for i in {1..20}; do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    echo "[OK] bascula-web ${PORT}"
    break
  fi
  sleep 0.5
done
if ! curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null; then
  journalctl -u bascula-web.service -n 200 --no-pager || true
  exit 1
fi

echo "[install-2-app] Servicios bascula-web y bascula-app activos"
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo "Mini-web: http://${IP:-<IP>}:${PORT}/"

sleep 3
if ! systemctl is-active --quiet bascula-app.service; then
  journalctl -u bascula-app -n 300 --no-pager || true
  tail -n 160 "/home/pi/.local/share/xorg/Xorg.0.log" 2>/dev/null || true
  echo "[ERR] bascula-app no ha arrancado" >&2
  exit 1
fi

pgrep -af "Xorg|startx" >/dev/null || { echo "[ERR] Xorg no está corriendo"; exit 1; }
pgrep -af "python .*bascula.ui.app" >/dev/null || { echo "[ERR] UI no detectada"; exit 1; }

echo "[OK] Mini-web y UI operativos"

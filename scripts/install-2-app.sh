#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
MARKER="/var/lib/bascula/install-1.done"

if [[ ! -f "${MARKER}" ]]; then
  echo "[install-2-app] ERROR: Ejecuta primero install-1-system.sh" >&2
  exit 1
fi

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  TARGET_USER="${TARGET_USER:-${SUDO_USER:-pi}}"
  exec sudo TARGET_USER="${TARGET_USER}" bash "$0" "$@"
fi

TARGET_USER="${TARGET_USER:-${SUDO_USER:-pi}}"

install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_USER}" "/home/${TARGET_USER}/.config/bascula"

SKIP_INSTALL_ALL_PACKAGES=1 \
SKIP_INSTALL_ALL_GROUPS=1 \
SKIP_INSTALL_ALL_XWRAPPER=1 \
SKIP_INSTALL_ALL_X11_TMPFILES=1 \
SKIP_INSTALL_ALL_EEPROM_CONFIG=1 \
SKIP_INSTALL_ALL_SERVICE_DEPLOY=1 \
PHASE=2 TARGET_USER="${TARGET_USER}" bash "${SCRIPT_DIR}/install-all.sh" "$@"

install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_USER}" /etc/bascula
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
install -D -m 0644 /dev/null /etc/bascula/APP_READY

install -D -m 0755 "${ROOT_DIR}/scripts/xsession.sh" /opt/bascula/current/scripts/xsession.sh
install -D -m 0755 "${ROOT_DIR}/scripts/net-fallback.sh" /opt/bascula/current/scripts/net-fallback.sh
install -D -m 0644 "${ROOT_DIR}/systemd/bascula-app.service" /etc/systemd/system/bascula-app.service
install -D -m 0644 "${ROOT_DIR}/systemd/bascula-web.service" /etc/systemd/system/bascula-web.service
install -D -m 0644 "${ROOT_DIR}/systemd/bascula-web.service.d/10-writable-home.conf" \
  /etc/systemd/system/bascula-web.service.d/10-writable-home.conf
install -D -m 0644 "${ROOT_DIR}/systemd/bascula-web.service.d/20-env-and-exec.conf" \
  /etc/systemd/system/bascula-web.service.d/20-env-and-exec.conf
install -D -m 0644 "${ROOT_DIR}/systemd/bascula-net-fallback.service" /etc/systemd/system/bascula-net-fallback.service

usermod -aG video,render,input "${TARGET_USER}" || true
loginctl enable-linger "${TARGET_USER}" || true

systemctl disable getty@tty1.service || true

systemctl daemon-reload
systemctl enable --now bascula-app.service || true
systemctl enable --now bascula-web.service || true
systemctl enable --now bascula-net-fallback.service || true

. /etc/default/bascula
PORT="${BASCULA_MINIWEB_PORT:-${BASCULA_WEB_PORT:-8080}}"

if ss -ltn "( sport = :${PORT} )" | grep -q ":${PORT}"; then
  echo "[install-2-app] AVISO: el puerto ${PORT} ya está en uso" >&2
fi

for i in {1..20}; do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    echo "[OK] bascula-web ${PORT}"
    break
  fi
  sleep 0.5
done

if ! curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null; then
  echo "[install-2-app] ERROR: mini-web no responde en /health" >&2
  journalctl -u bascula-web.service -n 200 --no-pager || true
  exit 1
fi

if ! systemctl is-active --quiet bascula-app.service; then
  echo "[install-2-app] ERROR: bascula-app no está activa" >&2
  journalctl -u bascula-app.service -n 200 --no-pager || true
  exit 1
fi

if ! pgrep -af "Xorg|startx" >/dev/null; then
  echo "[install-2-app] ERROR: Xorg/startx no está en ejecución" >&2
  journalctl -u bascula-app.service -n 200 --no-pager || true
  exit 1
fi

if ! pgrep -af "python .*bascula.ui.app" >/dev/null; then
  echo "[install-2-app] ERROR: Proceso de UI no detectado" >&2
  journalctl -u bascula-app.service -n 200 --no-pager || true
  exit 1
fi

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo "[install-2-app] Mini-web disponible en http://${IP:-<IP>}:${PORT}/"
echo "[install-2-app] UI y servicios operativos"

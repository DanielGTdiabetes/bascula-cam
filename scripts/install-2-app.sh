#!/usr/bin/env bash
: "${TARGET_USER:=pi}"
: "${FORCE_INSTALL_PACKAGES:=0}"

set -euxo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
MARKER="/var/lib/bascula/install-1.done"

# Requiere haber pasado por la parte 1
if [[ ! -f "${MARKER}" ]]; then
  echo "[ERR] Falta la parte 1 (install-1-system.sh). Aborto." >&2
  exit 1
fi

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  exec sudo TARGET_USER="${TARGET_USER}" FORCE_INSTALL_PACKAGES="${FORCE_INSTALL_PACKAGES}" bash "$0" "$@"
fi

TARGET_USER="${TARGET_USER:-${SUDO_USER:-pi}}"
TARGET_HOME="$(getent passwd "${TARGET_USER}" | cut -d: -f6)"

if [[ -z "${TARGET_HOME}" ]]; then
  echo "[ERR] Usuario ${TARGET_USER} no encontrado" >&2
  exit 1
fi

install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_USER}" "${TARGET_HOME}/.config/bascula"

# La parte 2 NO instala paquetes salvo que se fuerce explícitamente
if [[ "${FORCE_INSTALL_PACKAGES}" = "1" ]]; then
  apt-get update
  # (Opcional) instalar algún paquete extra específico de esta fase, si lo hay
fi

install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_USER}" /etc/bascula

{
  BASCULA_USER=${BASCULA_USER:-${TARGET_USER}}
  BASCULA_GROUP=${BASCULA_GROUP:-${TARGET_USER}}
  BASCULA_PREFIX=/opt/bascula/current
  BASCULA_VENV="${BASCULA_VENV:-/opt/bascula/current/.venv}"
  BASCULA_CFG_DIR="${BASCULA_CFG_DIR:-${TARGET_HOME}/.config/bascula}"
  BASCULA_RUNTIME_DIR=${BASCULA_RUNTIME_DIR:-/run/bascula}
  BASCULA_WEB_HOST=${BASCULA_WEB_HOST:-0.0.0.0}
  BASCULA_WEB_PORT=${BASCULA_WEB_PORT:-8080}
  BASCULA_MINIWEB_PORT=${BASCULA_MINIWEB_PORT:-${BASCULA_WEB_PORT}}
  FLASK_RUN_HOST=${FLASK_RUN_HOST:-0.0.0.0}

  # Fallback dev (no OTA instalado)
  if [[ ! -x "${BASCULA_VENV}/bin/python" && -x "${TARGET_HOME}/bascula-cam/.venv/bin/python" ]]; then
    echo "[inst] OTA venv no encontrado; usando fallback de desarrollo"
    BASCULA_PREFIX="${TARGET_HOME}/bascula-cam"
    BASCULA_VENV="${TARGET_HOME}/bascula-cam/.venv"
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
} > /etc/default/bascula

# --- Sincronización de assets y venv OTA ---
BASCULA_ROOT=/opt/bascula
BASCULA_CURRENT="${BASCULA_ROOT}/current"
BASCULA_SHARED="${BASCULA_ROOT}/shared"
BASCULA_VENV_DIR="${BASCULA_CURRENT}/.venv"

install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_USER}" "${BASCULA_ROOT}" "${BASCULA_CURRENT}" "${BASCULA_SHARED}"

SRC_REPO="${TARGET_HOME}/bascula-cam"
if [[ ! -d "${SRC_REPO}" ]]; then
  SRC_REPO="${ROOT_DIR}"
fi

rc=0
rsync -a --delete \
  --exclude ".git" --exclude ".venv" --exclude "__pycache__" --exclude "*.pyc" \
  --exclude '/assets' --exclude '/voices-v1' --exclude '/ota' \
  --exclude '/models' --exclude '/userdata' --exclude '/config' \
  "${SRC_REPO}/" "${BASCULA_CURRENT}/" || rc=$?
rc=${rc:-0}
if [[ $rc -ne 0 && $rc -ne 23 && $rc -ne 24 ]]; then
  exit "$rc"
fi

if [[ ! -x "${BASCULA_VENV_DIR}/bin/python" ]]; then
  python3 -m venv "${BASCULA_VENV_DIR}"
fi

if [[ ! -e "/opt/bascula/venv" ]]; then
  ln -s "${BASCULA_VENV_DIR}" /opt/bascula/venv 2>/dev/null || true
fi

if [[ -x "${BASCULA_VENV_DIR}/bin/pip" ]]; then
  export PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore PIP_PREFER_BINARY=1
  if [[ -f "${BASCULA_CURRENT}/requirements.txt" ]]; then
    "${BASCULA_VENV_DIR}/bin/pip" install --upgrade pip wheel setuptools
    "${BASCULA_VENV_DIR}/bin/pip" install -r "${BASCULA_CURRENT}/requirements.txt"
  fi
fi

install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_USER}" \
  "${BASCULA_SHARED}/assets" \
  "${BASCULA_SHARED}/voices-v1" \
  "${BASCULA_SHARED}/ota" \
  "${BASCULA_SHARED}/models" \
  "${BASCULA_SHARED}/userdata" \
  "${BASCULA_SHARED}/config"

LABELS_CACHE="${BASCULA_SHARED}/userdata/labels.json"
if [[ ! -f "${LABELS_CACHE}" ]]; then
  install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_USER}" "$(dirname "${LABELS_CACHE}")"
  printf '{}' > "${LABELS_CACHE}"
  chown "${TARGET_USER}:${TARGET_USER}" "${LABELS_CACHE}"
  chmod 0644 "${LABELS_CACHE}"
fi

shopt -s nullglob dotglob
for NAME in assets voices-v1 ota models userdata config; do
  SRC="${SRC_REPO}/${NAME}"
  SHARED_PATH="${BASCULA_SHARED}/${NAME}"
  LINK_PATH="${BASCULA_CURRENT}/${NAME}"

  if [[ -d "${LINK_PATH}" && ! -L "${LINK_PATH}" && ! -e "${SHARED_PATH}" ]]; then
    install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_USER}" "${SHARED_PATH}"
    rc=0
    rsync -a "${LINK_PATH}/" "${SHARED_PATH}/" || rc=$?
    rc=${rc:-0}
    if [[ $rc -ne 0 && $rc -ne 23 && $rc -ne 24 ]]; then
      exit "$rc"
    fi
  fi

  if [[ -d "${SRC}" ]]; then
    install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_USER}" "${SHARED_PATH}"
    rc=0
    rsync -a --delete "${SRC}/" "${SHARED_PATH}/" || rc=$?
    rc=${rc:-0}
    if [[ $rc -ne 0 && $rc -ne 23 && $rc -ne 24 ]]; then
      exit "$rc"
    fi
  fi

  rm -rf "${LINK_PATH}" 2>/dev/null || true
  ln -sfn "${SHARED_PATH}" "${LINK_PATH}"
  chown -h "${TARGET_USER}:${TARGET_USER}" "${LINK_PATH}" || true
done
shopt -u nullglob dotglob

chown -R "${TARGET_USER}:${TARGET_USER}" "${BASCULA_SHARED}"
chown -R "${TARGET_USER}:${TARGET_USER}" "${BASCULA_ROOT}"

for NAME in assets voices-v1 ota models userdata config; do
  test -L "${BASCULA_CURRENT}/${NAME}" || echo "[WARN] Falta symlink ${NAME}"
  test -d "${BASCULA_SHARED}/${NAME}" || echo "[INFO] ${NAME} vacío (no venía en OTA)"
done

# Copiado de units y scripts (sin heredocs)
install -D -m 0755 "${ROOT_DIR}/scripts/xsession.sh" /opt/bascula/current/scripts/xsession.sh
install -D -m 0755 "${ROOT_DIR}/scripts/net-fallback.sh" /opt/bascula/current/scripts/net-fallback.sh

install -D -m 0644 "${ROOT_DIR}/systemd/bascula-app.service" /etc/systemd/system/bascula-app.service
install -D -m 0644 "${ROOT_DIR}/systemd/bascula-web.service" /etc/systemd/system/bascula-web.service
install -D -m 0644 "${ROOT_DIR}/systemd/bascula-web.service.d/10-writable-home.conf" /etc/systemd/system/bascula-web.service.d/10-writable-home.conf
install -D -m 0644 "${ROOT_DIR}/systemd/bascula-web.service.d/20-env-and-exec.conf" /etc/systemd/system/bascula-web.service.d/20-env-and-exec.conf
install -D -m 0644 "${ROOT_DIR}/systemd/bascula-net-fallback.service" /etc/systemd/system/bascula-net-fallback.service

# Bandera de disponibilidad UI
install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_USER}" /etc/bascula
install -m 0644 /dev/null /etc/bascula/APP_READY

usermod -aG video,render,input "${TARGET_USER}" || true
loginctl enable-linger "${TARGET_USER}" || true

# Habilitación servicios
systemctl disable getty@tty1.service || true
systemctl daemon-reload
systemctl enable --now bascula-web.service bascula-net-fallback.service bascula-app.service

# Verificación mini-web
. /etc/default/bascula 2>/dev/null || true
PORT="${BASCULA_MINIWEB_PORT:-${BASCULA_WEB_PORT:-8080}}"
for i in {1..20}; do curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1 && break; sleep 0.5; done
curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null || { journalctl -u bascula-web -n 200 --no-pager || true; exit 1; }

# Verificación UI
sleep 3
systemctl is-active --quiet bascula-app.service || { journalctl -u bascula-app -n 300 --no-pager || true; exit 1; }
pgrep -af "Xorg|startx" >/dev/null || { echo "[ERR] Xorg no está corriendo"; exit 1; }
pgrep -af "python .*bascula.ui.app" >/dev/null || { echo "[ERR] UI no detectada"; exit 1; }

echo "[OK] Parte 2: UI, mini-web y AP operativos"

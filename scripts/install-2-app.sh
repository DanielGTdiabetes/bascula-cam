#!/usr/bin/env bash
: "${TARGET_USER:=pi}"
: "${FORCE_INSTALL_PACKAGES:=0}"

set -euo pipefail

# --- helpers para systemd opcional ---
have_systemd() {
  command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]
}

sctl() {
  if have_systemd; then
    # Propaga el exit status real de systemctl (para que set -e actúe en fallos reales)
    systemctl "$@"
  else
    echo "[info] systemd no está activo; omito: systemctl $*" >&2
    return 0
  fi
}

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

python3 -m venv "${BASCULA_VENV_DIR}"

# Ajustar permisos del venv para que no quede en root
if [[ -n "${TARGET_USER:-}" ]]; then
  chown -R "${TARGET_USER}:${TARGET_USER}" "${BASCULA_VENV_DIR}"
fi

if [[ ! -e "/opt/bascula/venv" ]]; then
  ln -s "${BASCULA_VENV_DIR}" /opt/bascula/venv 2>/dev/null || true
fi

if [[ -x "${BASCULA_VENV_DIR}/bin/pip" ]]; then
  export PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore PIP_PREFER_BINARY=1
  # shellcheck disable=SC1091
  source "${BASCULA_VENV_DIR}/bin/activate"

  pip install --upgrade pip wheel setuptools

  if ! pip install --only-binary=:all: "numpy==2.*"; then
    echo "[inst] No se encontró wheel para numpy==2.*; intentando build/alternativa" >&2
    pip install "numpy==2.*" || pip install numpy || true
  fi

  if [[ -f "${BASCULA_CURRENT}/requirements.txt" ]]; then
    req_rc=0
    pip install -r "${BASCULA_CURRENT}/requirements.txt" || req_rc=$?
    if [[ ${req_rc} -ne 0 ]]; then
      echo "[warn] pip install -r requirements.txt falló (rc=${req_rc}). Continuando para comprobar dependencias." >&2
    fi
  fi

  for pkg in "tflite-runtime==2.14.*" "opencv-python-headless>=4.8,<5"; do
    pkg_name="${pkg%%[<=>]*}"
    if ! pip show "${pkg_name}" >/dev/null 2>&1; then
      if ! pip install --only-binary=:all: "${pkg}"; then
        echo "[warn] Wheel no disponible para ${pkg}; intentando fallback" >&2
        pip install "${pkg}" || true
      fi
    fi
  done

  echo "[CHK] Verificando dependencias críticas..."
  if ! python - <<'PY'
try:
    from PIL import Image
    import numpy as np
    import cv2
    print("OK: PIL", Image.__version__)
    print("OK: numpy", np.__version__)
    print("OK: cv2", cv2.__version__)
except Exception as e:
    import sys, traceback
    print("ERR: Dependencias incompletas:", e, file=sys.stderr)
    traceback.print_exc()
    sys.exit(2)
PY
  then
    echo "[ERR] Faltan módulos en el venv; revisa requirements/deps." >&2
    deactivate || true
    exit 1
  fi

  if [[ -n "${TARGET_USER:-}" ]]; then
    chown -R "${TARGET_USER}:${TARGET_USER}" "${BASCULA_VENV_DIR}"
  fi

  deactivate || true
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
install -D -m 0755 "${ROOT_DIR}/scripts/recovery_xsession.sh" /opt/bascula/current/scripts/recovery_xsession.sh
install -D -m 0755 "${ROOT_DIR}/scripts/recovery_retry.sh" /opt/bascula/current/scripts/recovery_retry.sh
install -D -m 0755 "${ROOT_DIR}/scripts/recovery_update.sh" /opt/bascula/current/scripts/recovery_update.sh
install -D -m 0755 "${ROOT_DIR}/scripts/recovery_wifi.sh" /opt/bascula/current/scripts/recovery_wifi.sh
install -D -m 0755 "${ROOT_DIR}/scripts/ota.sh" /opt/bascula/current/scripts/ota.sh
install -D -m 0755 "${ROOT_DIR}/scripts/record_app_failure.sh" /opt/bascula/current/scripts/record_app_failure.sh

bash "${ROOT_DIR}/scripts/safe_run.sh"

install -D -m 0644 "${ROOT_DIR}/systemd/bascula-app.service" /etc/systemd/system/bascula-app.service
install -D -m 0644 "${ROOT_DIR}/systemd/bascula-app-failure@.service" /etc/systemd/system/bascula-app-failure@.service
install -D -m 0644 "${ROOT_DIR}/systemd/bascula-web.service" /etc/systemd/system/bascula-web.service
sctl daemon-reload                    # CRÍTICO: si systemd está activo y falla, aborta
# habilita/arranca servicios (CRÍTICO si hay systemd)
sctl enable --now bascula-app.service
sctl enable --now bascula-web.service
# reinicios adicionales pueden ser no críticos (por ejemplo, puerto ocupado); tolerarlos:
sctl restart bascula-web.service || echo "[warn] restart bascula-web falló; continúo" >&2
sctl restart bascula-app.service || echo "[warn] restart bascula-app falló; continúo" >&2
install -D -m 0644 "${ROOT_DIR}/systemd/bascula-net-fallback.service" /etc/systemd/system/bascula-net-fallback.service
install -D -m 0644 "${ROOT_DIR}/systemd/bascula-alarmd.service" /etc/systemd/system/bascula-alarmd.service
install -D -m 0644 "${ROOT_DIR}/systemd/bascula-recovery.service" /etc/systemd/system/bascula-recovery.service
install -D -m 0644 "${ROOT_DIR}/systemd/bascula-recovery.target" /etc/systemd/system/bascula-recovery.target
install -d -m 0755 /etc/polkit-1/rules.d
install -D -m 0644 "${ROOT_DIR}/polkit/10-bascula-nm.rules" /etc/polkit-1/rules.d/10-bascula-nm.rules

# Bandera de disponibilidad UI
install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_USER}" /etc/bascula
install -m 0644 /dev/null /etc/bascula/APP_READY
install -m 0644 /dev/null /etc/bascula/WEB_READY

LAST_CRASH="${BASCULA_SHARED}/userdata/last_crash.json"
if [[ ! -f "${LAST_CRASH}" ]]; then
  install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_USER}" "$(dirname "${LAST_CRASH}")"
  printf '{"timestamp": null}\n' > "${LAST_CRASH}"
  chown "${TARGET_USER}:${TARGET_USER}" "${LAST_CRASH}"
  chmod 0644 "${LAST_CRASH}"
fi

for grp in video render input; do
  if ! getent group "${grp}" >/dev/null 2>&1; then
    groupadd "${grp}" || true
  fi
done
usermod -aG video,render,input "${TARGET_USER}" || true
loginctl enable-linger "${TARGET_USER}" || true

# Habilitación servicios
. /etc/default/bascula 2>/dev/null || true
PORT="${BASCULA_MINIWEB_PORT:-${BASCULA_WEB_PORT:-8080}}"

if command -v fuser >/dev/null 2>&1; then
  fuser -k "${PORT}/tcp" 2>/dev/null || true
fi

sctl disable getty@tty1.service
sctl daemon-reload
sctl enable bascula-web.service bascula-net-fallback.service bascula-app.service bascula-alarmd.service
sctl restart bascula-web.service || echo "[warn] restart bascula-web falló; continúo" >&2
sctl restart bascula-alarmd.service || echo "[warn] restart bascula-alarmd falló; continúo" >&2
sctl restart bascula-net-fallback.service || echo "[warn] restart bascula-net-fallback falló; continúo" >&2
sctl restart bascula-app.service || echo "[warn] restart bascula-app falló; continúo" >&2

# Verificación mini-web
miniweb_ok=0
for attempt in {1..8}; do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    miniweb_ok=1
    break
  fi
  sleep "${attempt}"
done
if [[ ${miniweb_ok} -ne 1 ]]; then
  echo "[ERR] Mini-web: Not responding" >&2
  journalctl -u bascula-web -n 200 --no-pager || true
  exit 1
fi

# Verificación UI
sleep 3
if have_systemd; then
  if ! sctl is-active --quiet bascula-app.service; then
    journalctl -u bascula-app -n 300 --no-pager || true
    exit 1
  fi
fi
pgrep -af "Xorg|startx" >/dev/null || { echo "[ERR] Xorg no está corriendo"; exit 1; }
pgrep -af "python .*bascula.ui.app" >/dev/null || { echo "[ERR] UI no detectada"; exit 1; }

# Prueba rápida de Piper (no bloqueante, ignora errores)
if [[ -x "${BASCULA_VENV_DIR}/bin/python" ]]; then
  "${BASCULA_VENV_DIR}/bin/python" - <<'PY' || true
import time
import logging

logging.basicConfig(level=logging.INFO)

try:
    from bascula.services.voice import VoiceService
    VoiceService().speak("Prueba de voz")
    time.sleep(1.0)
    print("[inst] Piper speak ejecutado")
except Exception as exc:  # pragma: no cover - diagnóstico en instalación
    print(f"[WARN] Piper no disponible: {exc}")
PY
fi

set +e
bash "${ROOT_DIR}/scripts/smoke.sh"
smoke_rc=$?
set -e
if [[ ${smoke_rc} -ne 0 ]]; then
  echo "[WARN] smoke.sh falló (ver salida superior)" >&2
fi

echo "[OK] Parte 2: UI, mini-web y AP operativos"

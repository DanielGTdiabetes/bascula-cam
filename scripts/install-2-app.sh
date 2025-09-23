#!/usr/bin/env bash
: "${TARGET_USER:=pi}"
: "${FORCE_INSTALL_PACKAGES:=0}"

set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
MARKER="/var/lib/bascula/install-1.done"

if [[ "${BASCULA_CI:-0}" == "1" ]]; then
  export DESTDIR="${DESTDIR:-/tmp/ci-root}"
  mock_systemctl="${SYSTEMCTL:-${ROOT_DIR}/ci/mocks/systemctl}"
  if [[ -x "${mock_systemctl}" ]]; then
    export SYSTEMCTL="${mock_systemctl}"
  else
    export SYSTEMCTL="${SYSTEMCTL:-/bin/systemctl}"
  fi
else
  export SYSTEMCTL="${SYSTEMCTL:-/bin/systemctl}"
fi

# --- helpers para systemd opcional ---
have_systemd() {
  command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]
}

sctl() {
  local bin="${SYSTEMCTL}"
  if [[ -n "${SYSTEMCTL}" && "${BASCULA_CI:-0}" == "1" ]]; then
    "${bin}" "$@"
    return $?
  fi

  if have_systemd; then
    "${bin}" "$@"
    return $?
  fi

  echo "[info] systemd no está activo; omito: systemctl $*" >&2
  return 0
}

# Requiere haber pasado por la parte 1
if [[ "${BASCULA_CI:-0}" == "1" ]]; then
  if [[ ! -f "${DESTDIR}${MARKER}" ]]; then
    echo "[WARN] install-1 marker no encontrado en CI; creando marcador" >&2
    install -d -m 0755 "${DESTDIR}/var/lib/bascula"
    printf 'ok\n' > "${DESTDIR}${MARKER}"
  fi
else
  if [[ ! -f "${MARKER}" ]]; then
    echo "[ERR] Falta la parte 1 (install-1-system.sh). Aborto." >&2
    exit 1
  fi
fi

if [[ "${BASCULA_CI:-0}" == "1" ]]; then
  install -d -m 0755 "${DESTDIR}/etc/bascula"
  install -d -m 0755 "${DESTDIR}/etc/systemd/system"
  rm -rf "${DESTDIR}/opt/bascula/current/scripts"
  install -d -m 0755 "${DESTDIR}/opt/bascula/current/scripts"
  install -d -m 0755 "${DESTDIR}/opt/bascula/shared/userdata"
  install -d -m 0755 "${DESTDIR}/var/log/bascula"
  touch "${DESTDIR}/etc/bascula/APP_READY"
  touch "${DESTDIR}/etc/bascula/WEB_READY"
  install -D -m 0644 "${ROOT_DIR}/systemd/bascula-app.service" \
    "${DESTDIR}/etc/systemd/system/bascula-app.service"
  echo "[OK] install-2-app (CI)"
  exit 0
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

if [[ "${BASCULA_CI:-0}" != "1" ]]; then
  LOG_FILE="/var/log/bascula-install-2.log"
  install -d -m 0755 "$(dirname "${LOG_FILE}")"
  exec > >(tee -a "${LOG_FILE}")
  exec 2>&1
  echo "[inst] Log guardado en ${LOG_FILE}"
fi

echo "[inst] Instalando paquetes APT base"
apt-get update
apt-get install -y \
  python3-venv python3-pip python3-tk \
  python3-picamera2 python3-libcamera python3-simplejpeg libcamera-tools \
  build-essential python3-dev libjpeg-dev pkg-config \
  libcap-dev curl jq xinit fonts-dejavu-core

python3 - <<'PY'
try:
    from picamera2 import Picamera2
    print("OK: picamera2")
except Exception as e:
    print("ERR:", e)
    raise SystemExit(1)
PY

install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_USER}" "${TARGET_HOME}/.config/bascula"

install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_USER}" /var/log/bascula
touch /var/log/bascula/app.log
chown "${TARGET_USER}:${TARGET_USER}" /var/log/bascula/app.log
chmod 0644 /var/log/bascula/app.log

# Configuración mínima para Xorg rootless
install -d -m 0755 /etc/X11
printf 'allowed_users=anybody\n' > /etc/X11/Xwrapper.config
cat > "/home/${TARGET_USER}/.xserverrc" <<'EOF'
exec /usr/lib/xorg/Xorg :0 vt1 -nolisten tcp -noreset
EOF
chown "${TARGET_USER}:${TARGET_USER}" "/home/${TARGET_USER}/.xserverrc"
chmod +x "/home/${TARGET_USER}/.xserverrc"

# Paquetes adicionales sólo si se fuerza explícitamente
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

APP_VENV="${BASCULA_VENV_DIR}"
if [[ -d "${APP_VENV}" ]]; then
  OLD_VENV="${APP_VENV}.old.$(date +%s)"
  echo "[inst] Venv existente encontrado; renombrando a ${OLD_VENV}"
  mv "${APP_VENV}" "${OLD_VENV}"
  nohup rm -rf "${APP_VENV}.old."* >/dev/null 2>&1 &
fi

python3 -m venv "${APP_VENV}"

if [[ ! -e "/opt/bascula/venv" ]]; then
  ln -s "${BASCULA_VENV_DIR}" /opt/bascula/venv 2>/dev/null || true
fi

if [[ -x "${APP_VENV}/bin/python" ]]; then
  VENV_SITE_PACKAGES="$("${APP_VENV}/bin/python" - <<'PY'
import sysconfig
print(sysconfig.get_paths()["purelib"])
PY
)"
  if [[ -n "${VENV_SITE_PACKAGES}" ]]; then
    install -d -m 0755 "${VENV_SITE_PACKAGES}"
    readarray -t PICAMERA2_PATHS < <(python3 - <<'PY'
import pathlib
import importlib.util

spec = importlib.util.find_spec("picamera2")
if spec is None or spec.origin is None:
    raise SystemExit(0)
pkg_dir = pathlib.Path(spec.origin).parent
print(pkg_dir)
for candidate in pkg_dir.parent.glob("picamera2-*.dist-info"):
    print(candidate)
    break
PY
)
    PICAMERA2_DIR="${PICAMERA2_PATHS[0]:-}"
    PICAMERA2_DIST="${PICAMERA2_PATHS[1]:-}"
    if [[ -n "${PICAMERA2_DIR}" && -d "${PICAMERA2_DIR}" ]]; then
      echo "[inst] Copiando picamera2 del sistema al venv"
      rsync -a --delete "${PICAMERA2_DIR}/" "${VENV_SITE_PACKAGES}/picamera2/"
    fi
    if [[ -n "${PICAMERA2_DIST}" && -d "${PICAMERA2_DIST}" ]]; then
      rsync -a --delete "${PICAMERA2_DIST}/" "${VENV_SITE_PACKAGES}/$(basename "${PICAMERA2_DIST}")/"
    fi

    readarray -t LIBCAMERA_PATHS < <(python3 - <<'PY'
import pathlib
import importlib.util

spec = importlib.util.find_spec("libcamera")
if spec is None or spec.origin is None:
    raise SystemExit(0)
origin = pathlib.Path(spec.origin)
if origin.name == "__init__.py":
    pkg_dir = origin.parent
else:
    pkg_dir = origin
print(pkg_dir)
for candidate in pkg_dir.parent.glob("libcamera-*.dist-info"):
    print(candidate)
    break
PY
)
    LIBCAMERA_DIR="${LIBCAMERA_PATHS[0]:-}"
    LIBCAMERA_DIST="${LIBCAMERA_PATHS[1]:-}"
    if [[ -n "${LIBCAMERA_DIR}" ]]; then
      echo "[inst] Copiando libcamera del sistema al venv"
      if [[ -d "${LIBCAMERA_DIR}" ]]; then
        rsync -a --delete "${LIBCAMERA_DIR}/" "${VENV_SITE_PACKAGES}/$(basename "${LIBCAMERA_DIR}")/"
      elif [[ -f "${LIBCAMERA_DIR}" ]]; then
        install -D -m 0644 "${LIBCAMERA_DIR}" "${VENV_SITE_PACKAGES}/$(basename "${LIBCAMERA_DIR}")"
      fi
    fi
    if [[ -n "${LIBCAMERA_DIST}" && -d "${LIBCAMERA_DIST}" ]]; then
      rsync -a --delete "${LIBCAMERA_DIST}/" "${VENV_SITE_PACKAGES}/$(basename "${LIBCAMERA_DIST}")/"
    fi
  fi

  export PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore PIP_PREFER_BINARY=1 PYTHONNOUSERSITE=1
  VENV_PYTHON="${APP_VENV}/bin/python"
  VENV_PIP="${APP_VENV}/bin/pip"

  echo "[inst] Actualizando pip y wheel en el venv"
  "${VENV_PIP}" install --upgrade pip wheel

  echo "[inst] Fijando ABI estable (NumPy 1.24.4 + OpenCV 4.8.1.78)"
  "${VENV_PIP}" install 'numpy==1.24.4' 'opencv-python-headless==4.8.1.78'

  echo "[inst] Installing simplejpeg (wheel if available, else build)"
  if ! "${VENV_PIP}" install --only-binary=:all: simplejpeg; then
    echo "[inst] simplejpeg wheel no disponible; instalando toolchain y compilando"
    apt-get update
    apt-get install -y build-essential python3-dev libjpeg-dev
    "${VENV_PIP}" install --ignore-installed --no-binary=:all: simplejpeg
  fi

  REQUIREMENTS_FILE="${BASCULA_CURRENT}/requirements.txt"
  if [[ -f "${REQUIREMENTS_FILE}" ]]; then
    echo "[inst] Instalando requirements desde ${REQUIREMENTS_FILE}"
    "${VENV_PIP}" install -r "${REQUIREMENTS_FILE}"
  fi

  echo "[CHK] Verificando NumPy/OpenCV/simplejpeg, Picamera2 y Tk dentro del venv"
  if ! sudo -u "${TARGET_USER}" PYTHONNOUSERSITE=1 "${VENV_PYTHON}" - <<'PY'
import sys, site, numpy, cv2, simplejpeg, tkinter
print("PY", sys.version.split()[0], "| NumPy", numpy.__version__, "| cv2", cv2.__version__)
print("simplejpeg at:", simplejpeg.__file__)
assert "/.venv/" in simplejpeg.__file__, "simplejpeg no carga desde el venv (está usando el del sistema)"
from picamera2 import Picamera2
print("Picamera2 import OK")
print("Tk version:", tkinter.TkVersion)
PY
  then
    echo "[ERR] Falló la verificación del entorno Python" >&2
    exit 1
  fi

  if [[ -n "${TARGET_USER:-}" ]]; then
    chown -R "${TARGET_USER}:${TARGET_USER}" "${BASCULA_VENV_DIR}"
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
# Saneado X antes de arrancar (evita "Server is already active for display 0")
pkill -9 Xorg 2>/dev/null || true
rm -f /tmp/.X0-lock
rm -rf /tmp/.X11-unix
install -d -m 1777 /tmp/.X11-unix
PYTHONPATH="${ROOT_DIR}" python3 -m scripts.write_icons --out /opt/bascula/current/assets/icons || true
PYTHONPATH="${ROOT_DIR}" python3 -m scripts.validate_assets || true
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
touch /etc/bascula/APP_READY
touch /etc/bascula/WEB_READY
chmod 0644 /etc/bascula/APP_READY /etc/bascula/WEB_READY

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

if [[ -x "${BASCULA_VENV_DIR}/bin/python" ]]; then
  if ! sudo -u "${TARGET_USER}" TFLITE_OPTIONAL="${TFLITE_OPTIONAL:-0}" \
      "${BASCULA_VENV_DIR}/bin/python" "${ROOT_DIR}/scripts/check_python_deps.py"; then
    echo "[ERR] Dependencias Python faltantes; abortando instalación." >&2
    exit 1
  fi
fi

set +e
bash "${ROOT_DIR}/scripts/smoke.sh"
smoke_rc=$?
set -e
if [[ ${smoke_rc} -ne 0 ]]; then
  echo "[WARN] smoke.sh falló (ver salida superior)" >&2
fi

echo "[CHK] Servicios"
systemctl --no-pager --plain --failed || true
echo "[CHK] libcamera smoke"
if command -v libcamera-still >/dev/null; then
  if libcamera-still -n -o /tmp/bascula-smoke.jpg && [ -s /tmp/bascula-smoke.jpg ]; then
    echo "libcamera OK"
  else
    echo "[WARN] libcamera-still no generó imagen" >&2
  fi
fi
rm -f /tmp/bascula-smoke.jpg 2>/dev/null || true

echo "[OK] Parte 2: UI, mini-web y AP operativos"

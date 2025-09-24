#!/usr/bin/env bash
: "${TARGET_USER:=pi}"

set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
STATE_DIR="${DESTDIR:-}/var/lib/bascula"
MARKER="${STATE_DIR}/install-1.done"

SYSTEMCTL_BIN="${SYSTEMCTL:-/bin/systemctl}"

log() {
  printf '[install-2] %s\n' "$*"
}

have_systemd() {
  [[ -d /run/systemd/system ]] && command -v "${SYSTEMCTL_BIN}" >/dev/null 2>&1
}

sctl() {
  if have_systemd; then
    "${SYSTEMCTL_BIN}" "$@"
  else
    log "systemd no disponible; omito systemctl $*"
  fi
}

require_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    exec sudo TARGET_USER="${TARGET_USER}" "$0" "$@"
  fi
}

require_phase1() {
  if [[ ! -f "${MARKER}" ]]; then
    echo "[ERR] Falta la fase 1 (install-1-system.sh)." >&2
    exit 1
  fi
}

resolve_user() {
  TARGET_USER="${TARGET_USER:-${SUDO_USER:-pi}}"
  TARGET_HOME="$(getent passwd "${TARGET_USER}" | cut -d: -f6)"
  if [[ -z "${TARGET_HOME}" ]]; then
    echo "[ERR] Usuario ${TARGET_USER} no encontrado" >&2
    exit 1
  fi
}

python_venv_exec() {
  local venv="$1"
  shift
  sudo -u "${TARGET_USER}" env \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PIP_PREFER_BINARY=1 \
    PYTHONNOUSERSITE=1 \
    "${venv}/bin/$1" "${@:2}"
}

create_venv() {
  local venv_dir="$1"
  if [[ -d "${venv_dir}" ]]; then
    local stamp="${venv_dir}.old.$(date +%s)"
    log "renombrando venv existente a ${stamp}"
    mv "${venv_dir}" "${stamp}"
    nohup rm -rf "${stamp}" >/dev/null 2>&1 &
  fi
  python3 -m venv "${venv_dir}"
  chown -R "${TARGET_USER}:${TARGET_USER}" "${venv_dir}"
}

ensure_simplejpeg() {
  local venv_dir="$1"
  if python_venv_exec "${venv_dir}" pip install --only-binary=:all: simplejpeg; then
    return 0
  fi
  log "simplejpeg wheel no disponible; compilando desde fuente"
  apt-get update
  apt-get install -y --no-install-recommends build-essential python3-dev libjpeg-dev pkg-config
  python_venv_exec "${venv_dir}" pip install --no-binary=:all: simplejpeg
}

add_dist_packages_pth() {
  local venv_dir="$1"
  sudo -u "${TARGET_USER}" "${venv_dir}/bin/python" - <<'PY'
import sysconfig
from pathlib import Path
site = Path(sysconfig.get_paths()["purelib"])
pth = site / "zz_system_dist_path.pth"
pth.write_text("/usr/lib/python3/dist-packages\n")
print(f"[install-2] .pth añadido: {pth}")
PY
}

prepare_requirements() {
  local src_file="$1"
  local out_file="$2"
  python3 - "$src_file" "$out_file" <<'PY'
import pathlib
import sys

src = pathlib.Path(sys.argv[1])
dst = pathlib.Path(sys.argv[2])
if not src.exists():
    dst.write_text("")
    sys.exit(0)
lines = src.read_text().splitlines()
patched = []
for line in lines:
    if line.strip().startswith("tflite-runtime==2.14.0"):
        patched.append('tflite-runtime==2.14.0; platform_machine == "aarch64"')
    else:
        patched.append(line)
dst.write_text("\n".join(patched) + ("\n" if patched else ""))
PY
}

install_requirements() {
  local venv_dir="$1"
  local requirements_path="$2"
  if [[ ! -f "${requirements_path}" ]]; then
    return
  fi
  local tmp
  tmp="$(mktemp)"
  prepare_requirements "${requirements_path}" "${tmp}"
  python_venv_exec "${venv_dir}" pip install -r "${tmp}"
  rm -f "${tmp}"
}

write_x735_poweroff() {
  install -D -m 0755 -o root -g root "${ROOT_DIR}/scripts/x735-poweroff.sh" /usr/local/sbin/x735-poweroff.sh
  install -D -m 0644 /dev/null /etc/default/x735-poweroff
  cat > /etc/default/x735-poweroff <<'EOF'
# Configuración de apagado seguro para Geekworm x735 v3
X735_POWER_BUTTON_GPIO=4
X735_POWER_BUTTON_ACTIVE=0
X735_DEBOUNCE_SECONDS=2
X735_POLL_SECONDS=1
X735_POWER_COMMAND=/sbin/poweroff
X735_LOW_VOLTAGE_MV=5000
EOF
  cat > /etc/systemd/system/x735-poweroff.service <<'UNIT'
[Unit]
Description=Geekworm x735 v3 safe poweroff monitor
After=multi-user.target

[Service]
Type=simple
EnvironmentFile=-/etc/default/x735-poweroff
ExecStart=/usr/local/sbin/x735-poweroff.sh
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
UNIT
  if have_systemd; then
    sctl daemon-reload
    sctl enable --now x735-poweroff.service
  fi
}

configure_audio() {
  cat > /etc/asound.conf <<'EOF'
pcm.!default {
  type asym
  playback.pcm {
    type hw
    card 0
  }
  capture.pcm {
    type hw
    card 1
  }
}
ctl.!default {
  type hw
  card 0
}
EOF
}

download_piper_voice() {
  local models_dir="/opt/piper/models"
  local model_file="${models_dir}/es_ES-sharvard-medium.onnx"
  install -d -m 0755 "${models_dir}"
  if [[ ! -f "${model_file}" ]]; then
    local url="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/es/es_ES-sharvard-medium.onnx?download=1"
    log "descargando modelo Piper español"
    if ! curl -L --fail --output "${model_file}.tmp" "${url}"; then
      rm -f "${model_file}.tmp"
      echo "[ERR] No se pudo descargar el modelo Piper" >&2
      exit 1
    fi
    mv "${model_file}.tmp" "${model_file}"
  fi
}

repair_and_copy_icons() {
  local output
  output="$(PYTHONPATH="${ROOT_DIR}" python3 "${ROOT_DIR}/scripts/repair_icons.py")"
  printf '%s\n' "${output}"
  if ! grep -q '\[DONE\]' <<<"${output}"; then
    echo "[ERR] repair_icons.py no devolvió [DONE]" >&2
    exit 1
  fi
  local dest="/opt/bascula/shared/assets/icons"
  install -d -m 0755 "${dest}"
  find "${dest}" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
  tar -C "${ROOT_DIR}/assets/icons" -cf - . | tar -C "${dest}" -xf -
}

write_bascula_web_wrapper() {
  cat > /usr/local/bin/bascula-web <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
: "${VENV:=/opt/bascula/current/.venv}"
: "${APP:=/opt/bascula/current}"
PYTHON="${VENV}/bin/python"
if [[ ! -x "${PYTHON}" ]]; then
  echo "bascula-web: venv no encontrado en ${VENV}" >&2
  exit 1
fi
modules=(bascula.miniweb bascula.web bascula.app)
for module in "${modules[@]}"; do
  if "${PYTHON}" - <<'PY'
import importlib.util
import sys
spec = importlib.util.find_spec("${module}")
sys.exit(0 if spec else 1)
PY
  then
    exec env PYTHONPATH="${APP}" "${PYTHON}" -m "${module}"
  fi
done
echo "bascula-web: no se encontró módulo ejecutable" >&2
exit 1
EOF
  chmod 0755 /usr/local/bin/bascula-web
}

write_bascula_web_service() {
  cat > /etc/systemd/system/bascula-web.service <<'UNIT'
[Unit]
Description=Bascula web server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/bascula/current
EnvironmentFile=-/etc/default/bascula
Environment=VENV=/opt/bascula/current/.venv
Environment=APP=/opt/bascula/current
ExecStart=/usr/local/bin/bascula-web
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
UNIT
  if command -v systemd-analyze >/dev/null 2>&1; then
    systemd-analyze verify /etc/systemd/system/bascula-web.service
  else
    log "systemd-analyze no disponible"
  fi
  if have_systemd; then
    sctl daemon-reload
    sctl enable --now bascula-web.service
  fi
}

verify_python_stack() {
  local venv_dir="$1"
  python_venv_exec "${venv_dir}" python - <<'PY'
import numpy
import cv2
import simplejpeg
assert '/.venv/' in simplejpeg.__file__, simplejpeg.__file__
import libcamera
from picamera2 import Picamera2
print('Python stack OK', numpy.__version__, cv2.__version__)
PY
}

verify_uart() {
  if [[ ! -e /dev/serial0 ]]; then
    echo "[ERR] /dev/serial0 no existe" >&2
    exit 1
  fi
  if have_systemd; then
    if "${SYSTEMCTL_BIN}" is-enabled --quiet serial-getty@serial0.service; then
      echo "[ERR] serial-getty@serial0.service sigue habilitado" >&2
      exit 1
    fi
  fi
}

verify_services() {
  local svc
  for svc in x735-poweroff.service bascula-web.service; do
    if have_systemd; then
      if ! "${SYSTEMCTL_BIN}" is-active --quiet "${svc}"; then
        "${SYSTEMCTL_BIN}" status "${svc}" --no-pager
        exit 1
      fi
    else
      log "systemd no disponible; omito estado de ${svc}"
    fi
  done
}

verify_audio() {
  if command -v aplay >/dev/null 2>&1; then
    if ! aplay -q /usr/share/sounds/alsa/Front_Center.wav; then
      echo "[ERR] aplay falló" >&2
      exit 1
    fi
  fi
  if command -v espeak-ng >/dev/null 2>&1; then
    if ! timeout 5 espeak-ng -v es "Prueba de audio bascula" >/dev/null 2>&1; then
      echo "[ERR] espeak-ng falló" >&2
      exit 1
    fi
  fi
}

main() {
  require_root "$@"
  require_phase1
  resolve_user

  install -d -m 0755 "${STATE_DIR}"

  BASCULA_ROOT="/opt/bascula"
  BASCULA_CURRENT="${BASCULA_ROOT}/current"
  BASCULA_SHARED="${BASCULA_ROOT}/shared"
  BASCULA_VENV="${BASCULA_CURRENT}/.venv"

  install -d -m 0755 "${BASCULA_ROOT}" "${BASCULA_CURRENT}" "${BASCULA_SHARED}/assets"
  chown -R "${TARGET_USER}:${TARGET_USER}" "${BASCULA_ROOT}"

  # REPO_ROOT="${REPO_ROOT:-$(pwd)}"  # Comportamiento anterior (referencia histórica)
  # Ruta del script -> repo root (asumiendo scripts/ como subcarpeta del repo)
  REPO_ROOT="${REPO_ROOT:-${ROOT_DIR}}"
  RUNTIME_ROOT="/opt/bascula/current"

  echo "[inst] REPO_ROOT=${REPO_ROOT}"
  echo "[inst] RUNTIME_ROOT=${RUNTIME_ROOT}"

  # Señales mínimas de que es el repo correcto
  [ -d "${REPO_ROOT}/.git" ] || [ -f "${REPO_ROOT}/pyproject.toml" ] || [ -f "${REPO_ROOT}/requirements.txt" ] || {
    echo "[ERR] REPO_ROOT no parece el repo (falta .git/pyproject/requirements). Usa REPO_ROOT=/ruta/al/repo" >&2
    exit 1
  }

  # Protección contra rsync de /
  [ "${REPO_ROOT}" != "/" ] || { echo "[ERR] REPO_ROOT es '/': abortando" >&2; exit 1; }

  PROTECT_DIRS=("data" "local" "models")
  sudo mkdir -p "${RUNTIME_ROOT}"
  for d in "${PROTECT_DIRS[@]}"; do
    sudo mkdir -p "${RUNTIME_ROOT}/${d}"
  done

  # Usa ALLOW_DELETE=1 ./scripts/install-2-app.sh o INSTALL_MODE=clean para limpiar con --delete
  if [ "${ALLOW_DELETE:-0}" = "1" ] || [ "${INSTALL_MODE:-}" = "clean" ]; then
    echo "[inst] rsync: modo CLEAN con --delete (dirs protegidos excluidos)"
    sudo rsync -a --delete \
      --info=stats \
      --exclude 'data/***' \
      --exclude 'local/***' \
      --exclude 'models/***' \
      "${REPO_ROOT}/" "${RUNTIME_ROOT}/"
  else
    echo "[inst] rsync: modo SAFE (sin --delete). Usa ALLOW_DELETE=1 para limpieza."
    sudo rsync -a \
      --info=stats \
      --exclude 'data/***' \
      --exclude 'local/***' \
      --exclude 'models/***' \
      "${REPO_ROOT}/" "${RUNTIME_ROOT}/"
  fi

  echo "[inst] rsync protected: data local models"

  chown -R "${TARGET_USER}:${TARGET_USER}" "${BASCULA_CURRENT}"

  create_venv "${BASCULA_VENV}"

  python_venv_exec "${BASCULA_VENV}" pip install --upgrade pip wheel
  python_venv_exec "${BASCULA_VENV}" pip install 'numpy==1.24.4' 'opencv-python-headless==4.8.1.78'
  ensure_simplejpeg "${BASCULA_VENV}"
  add_dist_packages_pth "${BASCULA_VENV}"
  install_requirements "${BASCULA_VENV}" "${BASCULA_CURRENT}/requirements.txt"

  write_x735_poweroff
  configure_audio
  download_piper_voice
  repair_and_copy_icons
  write_bascula_web_wrapper
  write_bascula_web_service

  verify_python_stack "${BASCULA_VENV}"
  verify_uart
  verify_services
  verify_audio

  log "Comprobando Piper"
  if [[ -x "${BASCULA_VENV}/bin/python" ]]; then
    sudo -u "${TARGET_USER}" "${BASCULA_VENV}/bin/python" - <<'PY' || true
try:
    import piper
    print('Piper importado correctamente')
except Exception as exc:  # pragma: no cover
    print(f'[WARN] Piper no disponible: {exc}')
PY
  fi

  echo "[CHK] USB microphone"
  arecord -l || true

  echo "[DONE] install-2-app completado"
}

main "$@"

#!/usr/bin/env bash
: "${TARGET_USER:=pi}"

set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
ROOT_DIR="$(cd -- "${SCRIPT_DIR}/.." && pwd -P)"
REPO_ROOT="${REPO_ROOT:-$ROOT_DIR}"
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
  local runtime_root="$3"

  local tmp_dir="${runtime_root}/tmp"
  sudo mkdir -p "${tmp_dir}"
  sudo chown -R "${TARGET_USER}:${TARGET_USER}" "${tmp_dir}"

  local req_file=""
  local cleanup_req=0

  if [[ -f "${requirements_path}" ]]; then
    req_file="$(sudo -u "${TARGET_USER}" mktemp "${tmp_dir}/reqs.XXXXXX")"
    cleanup_req=1
    prepare_requirements "${requirements_path}" "${req_file}"
  fi

  if [[ ! -f "${requirements_path}" || "${COMPOSE_REQS:-0}" = "1" ]]; then
    if [[ -z "${req_file}" ]]; then
      req_file="$(sudo -u "${TARGET_USER}" mktemp "${tmp_dir}/reqs.XXXXXX")"
      cleanup_req=1
    fi
    sudo -u "${TARGET_USER}" bash -c 'umask 022; cat > "$1"' _ "${req_file}" <<'EOF'
# Requisitos dinámicos para Bascula
tflite-runtime==2.14.0; platform_machine == "aarch64"
EOF
  fi

  if [[ -z "${req_file}" ]]; then
    return
  fi

  sudo -u "${TARGET_USER}" TMPDIR="${tmp_dir}" "${venv_dir}/bin/pip" install --no-input -r "${req_file}"

  sudo -u "${TARGET_USER}" find "${tmp_dir}" -type f -name 'reqs.*' -mmin +30 -delete || true

  if [[ ${cleanup_req} -eq 1 ]]; then
    rm -f "${req_file}"
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
  local meta_file="${model_file}.json"
  install -d -m 0755 "${models_dir}"
  if [[ -f "${model_file}" && -f "${meta_file}" ]]; then
    return 0
  fi
  log "descargando modelo Piper español"
  set +e
  curl -Lf -o "${model_file}" \
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/sharvard/medium/es_ES-sharvard-medium.onnx"
  local c1=$?
  curl -Lf -o "${meta_file}" \
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/sharvard/medium/es_ES-sharvard-medium.onnx.json"
  local c2=$?
  set -e
  if [[ ${c1} -ne 0 || ${c2} -ne 0 ]]; then
    echo "[WARN] Piper voice not fully downloaded (offline or network issue). TTS will be disabled until models are present." >&2
  fi
}

configure_startx_session() {
  install -D -m 0755 -o "${TARGET_USER}" -g "${TARGET_USER}" /dev/stdin "${TARGET_HOME}/.xserverrc" <<'EOF'
#!/bin/sh
exec /usr/lib/xorg/Xorg.wrap :0 vt1 -keeptty
EOF

  install -D -m 0755 -o "${TARGET_USER}" -g "${TARGET_USER}" /dev/stdin "${TARGET_HOME}/.xinitrc" <<'EOF'
#!/bin/sh
# Arranca Openbox en background (WM + helpers)
( exec openbox-session ) &
OB_PID=$!

# Helpers básicos (no críticos si ya están en autostart)
command -v unclutter >/dev/null 2>&1 && "$(command -v unclutter)" -idle 0.5 -root &

# Evita que se apague/expire la pantalla en kiosco
xset s off -dpms || true

# UI en primer plano; al salir, cerrar Openbox y propagar exit code
/opt/bascula/current/.venv/bin/python -m bascula.ui.app >>/var/log/bascula/app.log 2>&1
UI_STATUS=$?
kill "${OB_PID}" >/dev/null 2>&1 || true
wait "${OB_PID}" 2>/dev/null || true
exit "${UI_STATUS}"
EOF

  install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_USER}" "${TARGET_HOME}/.config/openbox"
  install -D -m 0755 -o "${TARGET_USER}" -g "${TARGET_USER}" /dev/stdin "${TARGET_HOME}/.config/openbox/autostart" <<'EOF'
#!/bin/sh
# (Opcional) otros helpers de escritorio
# command -v xsetroot >/dev/null 2>&1 && xsetroot -solid black &
EOF
  install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_USER}" "${TARGET_HOME}/.cache/openbox/sessions"
}

write_bascula_app_wrapper() {
  install -D -m 0755 "${ROOT_DIR}/scripts/bascula-app-wrapper.sh" /usr/local/bin/bascula-app
}

write_bascula_web_wrapper() {
  install -D -m 0755 "${ROOT_DIR}/scripts/bascula-web-wrapper.sh" /usr/local/bin/bascula-web
}

install_unit_files() {
  local unit
  for unit in "$@"; do
    install -D -m 0644 "${ROOT_DIR}/systemd/${unit}" \
      "/etc/systemd/system/${unit}"
  done
}

verify_unit_files() {
  if command -v systemd-analyze >/dev/null 2>&1; then
    local unit
    for unit in "$@"; do
      systemd-analyze verify "/etc/systemd/system/${unit}"
    done
  else
    log "systemd-analyze no disponible"
  fi
}

ensure_default_env_file() {
  install -d -m 0755 /etc/default
  if [[ ! -f /etc/default/bascula ]]; then
    cat >/etc/default/bascula <<'EOF'
BASCULA_WEB_PORT=8080
BASCULA_MINIWEB_PORT=8080
BASCULA_ENV=prod
EOF
  fi
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

run_post_install_checks() {
  local venv_dir="$1"
  if [[ -x "${venv_dir}/bin/python" ]]; then
    "${venv_dir}/bin/python" - <<'PY'
import numpy
import cv2
import simplejpeg
assert "/.venv/" in simplejpeg.__file__, "simplejpeg must be loaded from venv"
import libcamera
from picamera2 import Picamera2
print("[CHK] Python+Camera OK")
PY
  else
    echo "[WARN] Venv python no encontrado; omitiendo verificación de cámara" >&2
  fi

  if command -v systemd-analyze >/dev/null 2>&1; then
    systemd-analyze verify /etc/systemd/system/*.service
  else
    log "systemd-analyze no disponible; omito verificación global"
  fi

  if have_systemd; then
    sctl daemon-reload
    sctl enable --now bascula-web.service bascula-app.service
    sleep 6
    sctl is-active bascula-web.service >/dev/null || echo "[WARN] bascula-web not active yet; check journalctl"
    sctl is-active bascula-app.service >/dev/null || echo "[WARN] bascula-app not active yet; check journalctl"
  else
    log "systemd no disponible; omito enable/estado de servicios"
  fi

  if command -v loginctl >/dev/null 2>&1; then
    loginctl seat-status seat0 || true
  else
    echo "[WARN] loginctl no disponible" >&2
  fi

  if [[ -x /usr/lib/xorg/Xorg.wrap ]]; then
    local perms mode
    perms="$(stat -c '%A %n' /usr/lib/xorg/Xorg.wrap)"
    mode="$(stat -c '%a' /usr/lib/xorg/Xorg.wrap)"
    if [[ ${mode} =~ ^[4-7] ]]; then
      echo "[CHK] Xorg.wrap setuid correcto (${perms})"
    else
      echo "[WARN] Xorg.wrap sin setuid (${perms})" >&2
    fi
  else
    echo "[WARN] /usr/lib/xorg/Xorg.wrap no encontrado" >&2
  fi

  if [[ -x /usr/bin/Xorg ]]; then
    echo "[CHK] /usr/bin/Xorg presente"
  else
    echo "[WARN] /usr/bin/Xorg no encontrado" >&2
  fi

  local xorg_log="${TARGET_HOME}/.local/share/xorg/Xorg.0.log"
  if [[ -f "${xorg_log}" ]]; then
    if grep -q 'modesetting' "${xorg_log}"; then
      echo "[CHK] Xorg usa driver modesetting"
    else
      echo "[WARN] Xorg.0.log no menciona modesetting" >&2
    fi
    if grep -q 'Using config directory: "/etc/X11/xorg.conf.d"' "${xorg_log}"; then
      echo "[CHK] Xorg detecta /etc/X11/xorg.conf.d"
    else
      echo "[WARN] Xorg.0.log no muestra xorg.conf.d" >&2
    fi
  else
    echo "[WARN] No se encontró ${xorg_log}" >&2
  fi

  local drm_status_files=()
  shopt -s nullglob
  drm_status_files=(/sys/class/drm/card1-*/status)
  shopt -u nullglob
  if (( ${#drm_status_files[@]} > 0 )); then
    if grep -Eq 'HDMI-A-[12].* connected' "${drm_status_files[@]}" 2>/dev/null; then
      echo "[CHK] HDMI en card1 reportado como connected"
    else
      echo "[WARN] HDMI card1 no aparece como connected" >&2
    fi
  else
    echo "[WARN] No hay ficheros /sys/class/drm/card1-*/status" >&2
  fi

  if command -v aplay >/dev/null 2>&1; then
    aplay -D default /usr/share/sounds/alsa/Front_Center.wav 2>/dev/null || echo "[WARN] playback test skipped/failed"
  else
    echo "[WARN] aplay no disponible" >&2
  fi

  if command -v espeak-ng >/dev/null 2>&1; then
    echo "Hola, prueba de voz" | espeak-ng --stdout 2>/dev/null | aplay -D default 2>/dev/null || echo "[WARN] TTS test skipped/failed"
  else
    echo "[WARN] espeak-ng no disponible" >&2
  fi

  arecord -l || true

  aplay -l || echo "[WARN] ALSA devices not listed"

  if [[ -f /opt/piper/models/es_ES-sharvard-medium.onnx && -f /opt/piper/models/es_ES-sharvard-medium.onnx.json ]]; then
    echo "[CHK] Piper voice present"
  else
    echo "[WARN] Piper voice missing (offline?)"
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
  APP_VENV="${BASCULA_CURRENT}/.venv"

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

  create_venv "${APP_VENV}"

  python_venv_exec "${APP_VENV}" pip install --upgrade pip wheel
  python_venv_exec "${APP_VENV}" pip install 'numpy==1.24.4' 'opencv-python-headless==4.8.1.78'
  ensure_simplejpeg "${APP_VENV}"
  add_dist_packages_pth "${APP_VENV}"
  install_requirements "${APP_VENV}" "${BASCULA_CURRENT}/requirements.txt" "${RUNTIME_ROOT}"

  configure_audio
  download_piper_voice
  configure_startx_session

  # --- Icons sync (simple, determinista) ---
  SRC_ICONS="${REPO_ROOT}/assets/icons"
  DST_ICONS="/opt/bascula/shared/assets/icons"

  if [ -d "${SRC_ICONS}" ]; then
    install -d -m 0755 "${DST_ICONS}"
    rsync -a --delete "${SRC_ICONS}/" "${DST_ICONS}/"
    synced_count=$(find "${DST_ICONS}" -type f -name '*.png' -print | wc -l | tr -d '[:space:]')
    echo "[icons] synced ${synced_count} files"
  else
    echo "[WARN] icons source not found: ${SRC_ICONS}"
  fi

  "${APP_VENV}/bin/python" - <<'PY' || true
from pathlib import Path

root = Path("/opt/bascula/shared/assets/icons")
ok = True

if not root.exists():
    ok = False
    print("[WARN] icons directory missing for validation")
else:
    try:
        from PIL import Image  # type: ignore
    except Exception as exc:  # noqa: BLE001
        ok = False
        print("[WARN] Pillow not available for icon validation:", exc)
    else:
        for path in root.rglob("*.png"):
            try:
                with Image.open(path) as img:
                    img.verify()
            except Exception as exc:  # noqa: BLE001
                ok = False
                print("[WARN] invalid PNG:", path, exc)

print("[CHK] icons", "OK" if ok else "WARN")
PY
  # --- end icons ---

  write_bascula_app_wrapper
  write_bascula_web_wrapper
  ensure_default_env_file
  install_unit_files \
    bascula-app.service \
    bascula-alarmd.service \
    bascula-app-failure@.service \
    bascula-net-fallback.service \
    bascula-recovery.service \
    bascula-web.service
  if command -v systemd-analyze >/dev/null 2>&1; then
    systemd-analyze verify /etc/systemd/system/bascula-app.service
  else
    log "systemd-analyze no disponible; omito verificación de bascula-app.service"
  fi
  if have_systemd; then
    sctl daemon-reload
    sctl enable --now bascula-app.service
  else
    log "systemd no disponible; omito enable/arranque de bascula-app.service"
  fi
  verify_unit_files \
    bascula-app.service \
    bascula-alarmd.service \
    bascula-app-failure@.service \
    bascula-net-fallback.service \
    bascula-recovery.service \
    bascula-web.service
  verify_uart
  run_post_install_checks "${BASCULA_VENV}"

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

  echo "[DONE] install-2-app completado"
}

main "$@"

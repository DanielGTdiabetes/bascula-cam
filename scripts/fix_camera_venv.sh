#!/usr/bin/env bash
# fix_camera_venv.sh
# Parcha el entorno para que la cámara y el preview con Pillow (ImageTk) funcionen en la app.

set -euo pipefail

VENV="/opt/bascula/current/.venv"
SITE="$VENV/lib/python3.11/site-packages"
PTH="$SITE/system_dist.pth"

log() { echo -e "\e[1;34m[fix-camera]\e[0m $*"; }
warn() { echo -e "\e[1;33m[fix-camera]\e[0m $*"; }
err() { echo -e "\e[1;31m[fix-camera]\e[0m $*"; }

require_root() {
  if [[ $EUID -ne 0 ]]; then
    err "Ejecuta este script con sudo."
    exit 1
  fi
}

ensure_venv() {
  if [[ ! -x "$VENV/bin/python" ]]; then
    warn "VENV no existe en $VENV. Creando…"
    python3 -m venv "$VENV"
  fi
  "$VENV/bin/python" -c 'import sys; print(sys.version)'
}

apt_camera_deps() {
  log "Instalando dependencias APT para cámara y preview…"
  apt-get update -y
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3-picamera2 \
    libcamera-apps \
    python3-pil.imagetk \
    python3-tk
}

tune_venv_pip() {
  log "Actualizando pip/setuptools/wheel en el venv…"
  "$VENV/bin/python" -m pip install --upgrade --no-input pip setuptools wheel
}

clean_conflicts() {
  log "Eliminando posibles conflictos en el venv (numpy, Pillow, simplejpeg)…"
  "$VENV/bin/pip" uninstall -y numpy Pillow simplejpeg || true
}

install_python_pkgs() {
  log "Instalando/actualizando paquetes Python necesarios en el venv…"
  # Numpy >=2,<2.3 satisface opencv 4.12 en ARM64; Pillow aporta ImageTk (si compila).
  "$VENV/bin/pip" install --no-input --upgrade \
    "numpy>=2,<2.3" \
    pillow \
    simplejpeg || true
}

link_system_dist() {
  log "Asegurando que el venv ve los dist-packages del sistema…"
  mkdir -p "$SITE"
  cat >"$PTH" <<EOF
/usr/lib/python3/dist-packages
/usr/lib/python3.11/dist-packages
EOF
  echo "Creado $PTH"
}

verify_imports() {
  log "Verificando imports dentro del venv…"
  set +e
  source "$VENV/bin/activate"
  python - <<'PY'
import sys, importlib.util, traceback
print("Python:", sys.version)
try:
    from PIL import Image, ImageTk
    print("Pillow OK:", Image.__file__)
    print("ImageTk OK:", ImageTk.__file__)
except Exception as e:
    print("Pillow/ImageTk ERROR:", e)
    traceback.print_exc()

spec = importlib.util.find_spec("picamera2")
print("picamera2 spec:", spec)
PY
  deactivate
  set -e
}

rebuild_wrapper() {
  log "Actualizando wrapper de arranque X para usar el venv…"
  install -m 0755 /dev/stdin /usr/local/bin/bascula-xsession <<'WRAP'
#!/usr/bin/env bash
export DISPLAY=:0
export XDG_RUNTIME_DIR=/run/user/0
export QT_QPA_PLATFORM=xcb
export PYTHONUNBUFFERED=1

VENV="/opt/bascula/current/.venv"
if [ -x "$VENV/bin/python" ]; then
  exec "$VENV/bin/python" -m bascula.ui.app
else
  exec python3 -m bascula.ui.app
fi
WRAP
}

restart_services() {
  log "Reiniciando servicios de la báscula…"
  systemctl daemon-reload || true
  systemctl restart bascula-app.service || true
  sleep 2
  log "Logs recientes (buscando Pillow/ImageTk/camera):"
  journalctl -u bascula-app.service -n 200 --no-pager | \
    grep -i "pillow\|imagetk\|preview\|camera" || true
}

main() {
  require_root
  apt_camera_deps
  ensure_venv
  tune_venv_pip
  clean_conflicts
  install_python_pkgs
  link_system_dist
  verify_imports
  rebuild_wrapper
  restart_services
  log "Listo. Abre 'Escanear' en la app y verifica el preview."
}

main "$@"

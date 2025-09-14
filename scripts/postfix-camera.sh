#!/usr/bin/env bash
# Post-instalación para cámara en Báscula (Bookworm / Pi 5)
# - Asegura libcamera + Picamera2 del sistema
# - Puentea dist-packages del sistema dentro del venv
# - Reconstruye simplejpeg contra la versión de numpy del venv
# - Smoke tests y reinicio de la app

set -euo pipefail

log() { printf '\n[postfix] %s\n' "$*" >&2; }
die() { printf '\n[postfix][ERROR] %s\n' "$*" >&2; exit 1; }

CURRENT="/opt/bascula/current"
VENV="${CURRENT}/.venv"
PYTHON="${VENV}/bin/python"
PIP="${VENV}/bin/pip"

[[ -d "$CURRENT" ]] || die "No existe ${CURRENT}"
[[ -x "$PYTHON" ]] || die "No existe venv en ${VENV}"

# 0) Pausar la app para liberar la cámara
systemctl stop bascula-app.service || true

log "Actualizando APT e instalando dependencias del sistema…"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y \
  libcamera-apps \
  python3-picamera2 \
  build-essential python3-dev pkg-config \
  libjpeg62-turbo-dev

# 1) Puente: añadir dist-packages del sistema al venv (para ver picamera2)
log "Creando puente a dist-packages del sistema dentro del venv…"
PV="$("$PYTHON" - <<'PY'
import sys
print(f"python{sys.version_info.major}.{sys.version_info.minor}")
PY
)"
PTH="${VENV}/lib/${PV}/site-packages/system_dist.pth"
mkdir -p "$(dirname "$PTH")"
cat >"$PTH" <<EOF
/usr/lib/python3/dist-packages
/usr/lib/${PV}/dist-packages
EOF

# 2) Preparar el venv
log "Actualizando pip/setuptools/wheel dentro del venv…"
"$PIP" install -q --upgrade pip setuptools wheel

# 3) Evitar conflicto de simplejpeg del sistema
log "Eliminando simplejpeg del sistema (si está)…"
apt-get -y remove --purge python3-simplejpeg || true

# 4) Alinear numpy en el venv (no tocar si ya está ok)
log "Alineando numpy y Pillow en el venv…"
"$PIP" install -q --upgrade "numpy<2.3,>=2.0" pillow

# 5) Recompilar simplejpeg contra el numpy del venv
log "Instalando simplejpeg (compilado desde fuente)…"
"$PIP" install --no-binary=:all: --no-build-isolation simplejpeg

# 6) Comprobación de import de picamera2
log "Smoke test: import picamera2…"
"$PYTHON" - <<'PY'
import importlib.util
spec = importlib.util.find_spec("picamera2")
assert spec is not None, "picamera2 no localizado"
print("picamera2 OK →", spec.origin)
PY

# 7) Smoke test rápido de captura PNG (sin usar encoders JPEG)
log "Smoke test: captura PNG a /tmp/picam_test.png…"
"$PYTHON" - <<'PY'
from picamera2 import Picamera2
from PIL import Image
import time
cam = Picamera2()
cfg = cam.create_preview_configuration(main={"size": (1280, 720), "format": "XBGR8888"})
cam.configure(cfg)
cam.start(); time.sleep(1.2)
arr = cam.capture_array()
cam.stop()
Image.fromarray(arr).save("/tmp/picam_test.png")
print("OK → /tmp/picam_test.png", arr.shape, arr.dtype)
PY

ls -lh /tmp/picam_test.png || true

# 8) Prueba opcional con rpicam-still (sin preview)
log "Smoke test rpicam-still (opcional)…"
if command -v rpicam-still >/dev/null 2>&1; then
  rpicam-still -o /tmp/rpicam_test.jpg --timeout 1500 --nopreview || true
  ls -lh /tmp/rpicam_test.jpg || true
else
  log "rpicam-still no está en PATH (ok en Bookworm minimal)."
fi

# 9) Asegurar pertenencia al grupo video
USR="${SUDO_USER:-pi}"
log "Añadiendo ${USR} al grupo video (si hace falta)…"
usermod -aG video "$USR" || true

# 10) Reiniciar app
log "Reiniciando bascula-app.service…"
systemctl restart bascula-app.service || true

log "Listo ✅  (revisa que se haya creado /tmp/picam_test.png)"

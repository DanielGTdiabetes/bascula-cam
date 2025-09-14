#!/usr/bin/env bash
set -euo pipefail

# --- Config -------------------------------------------------------------
VENV_DEFAULT="/opt/bascula/current/.venv"
VENV="${1:-$VENV_DEFAULT}"

echo "[fix_camera_venv] VENV = $VENV"

if [[ ! -d "$VENV" || ! -x "$VENV/bin/python" ]]; then
  echo "[fix_camera_venv] ERROR: venv no existe: $VENV" >&2
  exit 1
fi

# --- 1) Paquetes de sistema necesarios ---------------------------------
echo "[fix_camera_venv] Instalando paquetes APT…"
sudo apt-get update -y
# rpicam-apps = herramientas libcamera en Bookworm (reemplaza libcamera-apps)
sudo apt-get install -y \
  rpicam-apps python3-picamera2 python3-pil python3-numpy python3-simplejpeg

# --- 2) Propiedad del venv (evita PermissionError) ---------------------
echo "[fix_camera_venv] Ajustando permisos del venv…"
sudo chown -R pi:pi "$VENV"

# --- 3) Asegurar que el venv NO use numpy de pip -----------------------
echo "[fix_camera_venv] Purga numpy/simplejpeg de pip dentro del venv (si existen)…"
# Usar el pip del venv con sudo para evitar bloqueos por permisos residuales
sudo "$VENV/bin/pip" uninstall -y numpy simplejpeg || true

# --- 4) Inyectar site-packages de sistema en el venv -------------------
echo "[fix_camera_venv] Añadiendo system site-packages al venv…"
PYVER=$("$VENV/bin/python" -c 'import sys;print(f"python{sys.version_info.major}.{sys.version_info.minor}")')
PTH="$VENV/lib/$PYVER/site-packages/system_dist.pth"
sudo tee "$PTH" >/dev/null <<EOF
/usr/lib/python3/dist-packages
/usr/lib/$PYVER/dist-packages
EOF
sudo chown pi:pi "$PTH"

# --- 5) Verificación rápida --------------------------------------------
echo "[fix_camera_venv] Verificación de imports…"
"$VENV/bin/python" - <<'PY'
import sys, importlib.util
ok_path = "/usr/lib/python3/dist-packages" in sys.path
print("  PATH incluye dist-packages?:", ok_path)
print("  Picamera2 spec:", importlib.util.find_spec("picamera2"))
import numpy, simplejpeg, PIL
print("  NUMPY:", numpy.__version__, "->", numpy.__file__)
print("  simplejpeg OK, PIL OK")
PY

# --- 6) Prueba de captura (sin GUI) ------------------------------------
echo "[fix_camera_venv] Prueba de captura /tmp/picam_ok.png …"
"$VENV/bin/python" - <<'PY'
from picamera2 import Picamera2
from PIL import Image
import time
cam = Picamera2()
cfg = cam.create_preview_configuration(main={"size": (640,480), "format": "XBGR8888"})
cam.configure(cfg); cam.start(); time.sleep(1.2)
arr = cam.capture_array(); cam.stop()
Image.fromarray(arr).save("/tmp/picam_ok.png")
print("  OK -> /tmp/picam_ok.png", arr.shape, arr.dtype)
PY
ls -lh /tmp/picam_ok.png || true
#!/usr/bin/env bash
set -euo pipefail

VENV="/opt/bascula/current/.venv"
APP_ENTRY="/usr/local/bin/bascula-xsession"

echo "[fix-camera] Asegurando wrapper de arranque con el venv…"
sudo tee "$APP_ENTRY" >/dev/null <<'SH'
#!/usr/bin/env bash
export PYTHONUNBUFFERED=1
export PYTHONPATH=/opt/bascula/current
exec /opt/bascula/current/.venv/bin/python -m bascula.ui.app
SH
sudo chmod +x "$APP_ENTRY"

echo "[fix-camera] Instalando Pillow en el venv…"
if [ -x "$VENV/bin/pip" ]; then
  "$VENV/bin/pip" install --upgrade --no-input Pillow
else
  echo "[fix-camera] ¡OJO! No encuentro pip en $VENV; ¿se creó el venv?"
fi

echo "[fix-camera] Instalando ImageTk del sistema (cobertura extra)…"
sudo apt-get update -y
sudo apt-get install -y python3-pil python3-pil.imagetk

echo "[fix-camera] Recargando systemd y reiniciando la app…"
sudo systemctl daemon-reload || true
sudo systemctl restart bascula-app.service || true

echo "[fix-camera] Diagnóstico rápido:"
sleep 2
PYEXE_PID=$(pgrep -f "python .*bascula\.ui\.app" | head -n1 || true)
if [ -n "${PYEXE_PID:-}" ] && [ -r "/proc/$PYEXE_PID/exe" ]; then
  echo "  python en ejecución: $(readlink -f /proc/$PYEXE_PID/exe)"
fi

echo "[fix_camera_venv] Hecho."

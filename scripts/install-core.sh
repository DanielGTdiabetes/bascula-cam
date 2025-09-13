#!/usr/bin/env bash
set -euo pipefail
#
# install-core.sh (FIXED) — Bascula-Cam core for Raspberry Pi 5, RPi OS Lite 64-bit
# - Venv 100% aislado
# - NumPy en venv == versión del sistema (evita ABI mismatch)
# - Picamera2 via APT + expuesto al venv con PYTHONPATH en services
# - Servicios systemd completos (ocr, mini-web, app)
# - Configuración KMS/I2S/PWM idempotente
# - Verificación dura de servicios + permisos finales
#
log()  { printf "\033[1;34m[core]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }
err()  { printf "\033[1;31m[ERR ]\033[0m %s\n" "$*"; }

require_root(){ if [[ ${EUID:-$(id -u)} -ne 0 ]]; then err "Ejecuta con sudo"; exit 1; fi; }
require_root

TARGET_USER="${TARGET_USER:-${SUDO_USER:-pi}}"
TARGET_GROUP="$(id -gn "$TARGET_USER")"
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"

BASCULA_ROOT="/opt/bascula"
REL_DIR="${BASCULA_ROOT}/releases"
CUR_LINK="${BASCULA_ROOT}/current"

if [[ -d /boot/firmware ]]; then BOOTDIR="/boot/firmware"; else BOOTDIR="/boot"; fi
CONF="${BOOTDIR}/config.txt"
CMDF="${BOOTDIR}/cmdline.txt"

HDMI_W="${HDMI_W:-1024}"; HDMI_H="${HDMI_H:-600}"; HDMI_FPS="${HDMI_FPS:-60}"

# Idempotencia básica
if [[ -L "${CUR_LINK}" && -d "${CUR_LINK}" ]]; then
  warn "Ya existe una release activa en ${CUR_LINK}. Elimina el symlink para reinstalar."
  exit 0
fi

apt-get update -y
log "Instalando paquetes base del sistema…"
apt-get install -y git curl ca-certificates build-essential cmake pkg-config \
  python3 python3-venv python3-pip python3-tk python3-serial python3-numpy \
  x11-xserver-utils xserver-xorg xinit openbox \
  unclutter fonts-dejavu libjpeg-dev zlib1g-dev libpng-dev \
  alsa-utils sox ffmpeg libzbar0 gpiod python3-rpi.gpio \
  network-manager sqlite3 tesseract-ocr tesseract-ocr-spa espeak-ng jq \
  libcamera-apps rpicam-apps python3-picamera2

# Detectar versión de numpy del sistema para anclar en venv
SYS_NUMPY="$(python3 - <<'PY'
import numpy; print(numpy.__version__)
PY
)"
log "NumPy del sistema: ${SYS_NUMPY}"

# Config.txt idempotente (KMS/I2S/PWM + UART limpio)
log "Actualizando ${CONF}…"
sed -i '/^# --- Bascula-Cam Core ---/,$d' "${CONF}"
{
  echo ""
  echo "# --- Bascula-Cam Core ---"
  echo "enable_uart=1"
  echo "hdmi_force_hotplug=1"
  echo "hdmi_group=2"
  echo "hdmi_mode=87"
  echo "hdmi_cvt=${HDMI_W} ${HDMI_H} ${HDMI_FPS} 3 0 0 0"
  echo "dtoverlay=vc4-kms-v3d"
  echo "dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4"
} >> "${CONF}"
# Limpiar consola serie en cmdline
if [[ -f "${CMDF}" ]]; then sed -i 's/console=serial0,115200 //g' "${CMDF}"; fi

# Grupos útiles
usermod -aG dialout,video,render "${TARGET_USER}" || true

# Clonar repo y preparar OTA
log "Clonando aplicación…"
install -d -m 0755 "${REL_DIR}"
DEST="${REL_DIR}/v1"
git clone https://github.com/DanielGTdiabetes/bascula-cam.git "${DEST}"
ln -s "${DEST}" "${CUR_LINK}"
chown -R "${TARGET_USER}:${TARGET_GROUP}" "${BASCULA_ROOT}"

# Venv aislado + dependencias
log "Creando venv aislado…"
cd "${CUR_LINK}"
python3 -m venv .venv
VENV_PY="${CUR_LINK}/.venv/bin/python"
VENV_PIP="${CUR_LINK}/.venv/bin/pip"
export PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore
export PIP_INDEX_URL="${PIP_INDEX_URL:-https://www.piwheels.org/simple}"
export PIP_EXTRA_INDEX_URL="${PIP_EXTRA_INDEX_URL:-https://pypi.org/simple}"
"${VENV_PY}" -m pip install --upgrade pip wheel setuptools
log "Instalando dependencias…"
"${VENV_PIP}" install "numpy==${SYS_NUMPY}" pyserial pillow "Flask>=2.2" fastapi "uvicorn[standard]" \
  pytesseract requests pyzbar "pytz>=2024.1" "opencv-python-headless<4.9"
# Cargar requirements.txt filtrando paquetes problemáticos
if [[ -f "requirements.txt" ]]; then
  TMP_REQ="$(mktemp)"
  grep -viE '^[[:space:]]*(numpy|picamera2|pymupdf|fitz)\b' requirements.txt > "${TMP_REQ}" || true
  if [[ -s "${TMP_REQ}" ]]; then "${VENV_PIP}" install -r "${TMP_REQ}"; fi
  rm -f "${TMP_REQ}"
fi

# OCR FastAPI app
install -d -m 0755 /opt/ocr-service
cat > /opt/ocr-service/app.py <<'PY'
import io
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, PlainTextResponse
from PIL import Image
import pytesseract
app = FastAPI(title="OCR Service", version="1.2")
@app.get("/", response_class=PlainTextResponse)
def root(): return "ok"
@app.get("/health")
def health(): return {"status": "ok"}
@app.post("/ocr")
async def ocr_endpoint(file: UploadFile = File(...), lang: str = Form("spa")):
    try:
        data = await file.read()
        img = Image.open(io.BytesIO(data))
        txt = pytesseract.image_to_string(img, lang=lang)
        return JSONResponse({"ok": True, "text": txt})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
PY

# Units systemd
cat > /etc/systemd/system/ocr-service.service <<'EOF'
[Unit]
Description=Bascula OCR Service (FastAPI)
After=network.target
[Service]
Type=simple
WorkingDirectory=/opt/ocr-service
ExecStart=/opt/bascula/current/.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8078
Restart=on-failure
[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/bascula-web.service <<EOF
[Unit]
Description=Bascula Mini-Web
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User=${TARGET_USER}
Group=${TARGET_GROUP}
WorkingDirectory=${CUR_LINK}
Environment="PYTHONUNBUFFERED=1" "BASCULA_WEB_HOST=0.0.0.0" "BASCULA_WEB_PORT=8080" "PYTHONPATH=/usr/lib/python3/dist-packages"
ExecStart=${CUR_LINK}/.venv/bin/python -m bascula.services.wifi_config
Restart=on-failure
RestartSec=2
[Install]
WantedBy=multi-user.target
EOF

install -d -m 0755 /usr/local/bin
cat > /usr/local/bin/bascula-xsession <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
export DISPLAY=:0
export PYTHONPATH=/usr/lib/python3/dist-packages
xset s off || true; xset -dpms || true; xset s noblank || true
unclutter -idle 0 -root &
cd /opt/bascula/current || exit 0
source .venv/bin/activate || true
if [[ -x "scripts/run-ui.sh" ]]; then exec scripts/run-ui.sh; fi
python3 -m bascula.ui.app || python3 -m bascula.ui.recovery_ui
EOF
chmod 0755 /usr/local/bin/bascula-xsession

cat > /etc/systemd/system/bascula-app.service <<EOF
[Unit]
Description=Bascula Digital Pro (UI en X)
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User=${TARGET_USER}
Group=${TARGET_GROUP}
WorkingDirectory=${CUR_LINK}
Environment="PYTHONPATH=/usr/lib/python3/dist-packages"
ExecStart=/usr/bin/xinit /usr/local/bin/bascula-xsession -- :0 vt1 -nolisten tcp
Restart=on-failure
RestartSec=3
[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now ocr-service.service
systemctl enable --now bascula-web.service
systemctl enable bascula-app.service

# Verificaciones duras
for i in {1..8}; do
  code="$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8078/ || echo 000)"
  [[ "$code" == "200" ]] && { log "OCR OK (:8078)"; break; }
  warn "OCR no responde (intento $i)"; sleep 2; systemctl restart ocr-service.service || true
done
code="$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8078/ || echo 000)"
[[ "$code" == "200" ]] || { err "OCR no arrancó correctamente"; exit 1; }

for i in {1..8}; do
  code="$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/ || echo 000)"
  [[ "$code" == "200" || "$code" == "404" ]] && { log "Mini-web vivo (:8080)"; break; }
  warn "Mini-web no responde (intento $i)"; sleep 2; systemctl restart bascula-web.service || true
done
code="$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/ || echo 000)"
[[ "$code" == "200" || "$code" == "404" ]] || { err "Mini-web no arrancó"; exit 1; }

# Permisos finales
install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_GROUP}" /var/log/bascula
chown -R "${TARGET_USER}:${TARGET_GROUP}" "${BASCULA_ROOT}" /opt/ocr-service || true

log "Instalación principal completada. Reinicia para aplicar KMS/I2S/PWM: sudo reboot"

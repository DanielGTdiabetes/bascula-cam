#!/usr/bin/env bash
set -euo pipefail
#
# scripts/install-all.sh — Bascula-Cam (Raspberry Pi 5, 4 GB) — FINAL (NM AP, ALL enabled)
# - Clona el repo en /opt/bascula/releases/v1 y apunta /opt/bascula/current
# - 1024x600 por defecto (HDMI CVT)
# - Piper + espeak-ng + say.sh
# - Mic USB + mic-test.sh
# - Cámara Pi 5 (libcamera0.5 + rpicam-apps + picamera2)
# - Xorg kiosco + systemd
# - IA SIEMPRE: ASR (whisper.cpp), OCR (Tesseract + FastAPI), Vision-lite (TFLite), OCR robusto (PaddleOCR)
# - WiFi AP fallback SIEMPRE con NetworkManager:
#   * Copia dispatcher desde el repo: scripts/nm-dispatcher/90-bascula-ap-fallback
#   * Crea/actualiza el perfil AP "BasculaAP" (ipv4.method shared)
#   * Habilita mini-web si existe (puerto 8080)
#   * SSID=Bascula_AP PASS=bascula1234 IFACE=wlan0
#

log()  { printf "\033[1;34m[inst]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }
err()  { printf "\033[1;31m[ERR ]\033[0m %s\n" "$*"; }

require_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    err "Ejecuta con sudo: sudo ./install-all.sh"
    exit 1
  fi
}
require_root

# --- Config AP por defecto ---
AP_SSID="${AP_SSID:-Bascula_AP}"
AP_PASS="${AP_PASS:-bascula1234}"
AP_IFACE="${AP_IFACE:-wlan0}"
AP_NAME="${AP_NAME:-BasculaAP}"

TARGET_USER="${TARGET_USER:-${SUDO_USER:-pi}}"
TARGET_GROUP="$(id -gn "$TARGET_USER")"
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"

BASCULA_ROOT="/opt/bascula"
BASCULA_RELEASES_DIR="${BASCULA_ROOT}/releases"
BASCULA_CURRENT_LINK="${BASCULA_ROOT}/current"
XSESSION="/usr/local/bin/bascula-xsession"
SERVICE="/etc/systemd/system/bascula-app.service"
XWRAPPER="/etc/X11/Xwrapper.config"
TMPFILES="/etc/tmpfiles.d/bascula.conf"
SAY_BIN="/usr/local/bin/say.sh"
MIC_TEST="/usr/local/bin/mic-test.sh"

HDMI_W="${HDMI_W:-1024}"
HDMI_H="${HDMI_H:-600}"
HDMI_FPS="${HDMI_FPS:-60}"

if [[ -d /boot/firmware ]]; then
  BOOTDIR="/boot/firmware"
else
  BOOTDIR="/boot"
fi
CONF="${BOOTDIR}/config.txt"

log "Usuario objetivo : $TARGET_USER ($TARGET_GROUP)"
log "HOME objetivo    : $TARGET_HOME"
log "OTA current link : $BASCULA_CURRENT_LINK"
log "AP (NM)          : SSID=${AP_SSID} PASS=${AP_PASS} IFACE=${AP_IFACE} perfil=${AP_NAME}"

apt-get update -y

# ---------- Paquetes base ----------
apt-get install -y git curl ca-certificates build-essential cmake pkg-config \
  python3 python3-venv python3-pip python3-tk \
  x11-xserver-utils xserver-xorg xinit openbox \
  unclutter fonts-dejavu \
  libjpeg-dev zlib1g-dev libpng-dev \
  alsa-utils sox ffmpeg \
  libzbar0 \
  network-manager sqlite3

# ---------- Limpieza libcamera antigua y preparación Pi 5 ----------
for p in libcamera0 libcamera-ipa libcamera-apps libcamera0.5 rpicam-apps python3-picamera2; do
  apt-mark unhold "$p" 2>/dev/null || true
done
if dpkg -l | grep -q "^ii.*libcamera0 "; then apt-get remove --purge -y libcamera0 || true; fi
apt-get autoremove -y || true
apt-get autoclean -y || true

# ---------- Cámara Pi 5 ----------
apt-get install -y --no-install-recommends libcamera-ipa libcamera0.5 || { err "libcamera 0.5"; exit 1; }
if ! apt-get install -y rpicam-apps; then apt-get install -y libcamera-apps; fi
apt-get install -y python3-picamera2
python3 - <<'PY' 2>/dev/null || true
from picamera2 import Picamera2
print("Picamera2 OK")
PY

# ---------- UART ----------
if [[ -f "${CONF}" ]] && ! grep -q "^enable_uart=1" "${CONF}"; then echo "enable_uart=1" >> "${CONF}"; fi
if [[ -f "${BOOTDIR}/cmdline.txt" ]]; then sed -i 's/console=serial0,115200 //g' "${BOOTDIR}/cmdline.txt" || true; fi
if command -v raspi-config >/dev/null 2>&1; then raspi-config nonint do_serial 0 || true; fi

# ---------- HDMI/KMS + I2S ----------
if [[ -f "${CONF}" ]]; then
  sed -i '/^hdmi_force_hotplug=/d;/^hdmi_group=/d;/^hdmi_mode=/d;/^hdmi_cvt=/d;/^dtoverlay=vc4-/d;/^dtparam=audio=/d;/^dtoverlay=i2s-mmap/d;/^dtoverlay=hifiberry-dac/d' "${CONF}"
  {
    echo ""
    echo "# --- Bascula-Cam (Pi 5): Video + Audio I2S ---"
    echo "hdmi_force_hotplug=1"
    echo "hdmi_group=2"
    echo "hdmi_mode=87"
    echo "hdmi_cvt=${HDMI_W} ${HDMI_H} ${HDMI_FPS} 3 0 0 0"
    echo "dtoverlay=vc4-kms-v3d"
    echo "dtparam=audio=off"
    echo "dtoverlay=i2s-mmap"
    echo "dtoverlay=hifiberry-dac"
  } >> "${CONF}"
fi

# ---------- Xwrapper ----------
install -d -m 0755 /etc/X11
cat > "${XWRAPPER}" <<'EOF'
allowed_users=anybody
needs_root_rights=yes
EOF

# ---------- OTA: releases/current ----------
install -d -m 0755 "${BASCULA_RELEASES_DIR}"
if [[ ! -e "${BASCULA_CURRENT_LINK}" ]]; then
  if git ls-remote https://github.com/DanielGTdiabetes/bascula-cam.git >/dev/null 2>&1; then
    log "Clonando repositorio en ${BASCULA_RELEASES_DIR}/v1…"
    git clone https://github.com/DanielGTdiabetes/bascula-cam.git "${BASCULA_RELEASES_DIR}/v1"
    ln -s "${BASCULA_RELEASES_DIR}/v1" "${BASCULA_CURRENT_LINK}"
  else
    err "No hay acceso a GitHub. Crea/ajusta ${BASCULA_CURRENT_LINK} manualmente y reintenta."
    exit 1
  fi
fi
chown -R "${TARGET_USER}:${TARGET_GROUP}" "${BASCULA_ROOT}"
install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_GROUP}" /var/log/bascula

# ---------- VENV + Python deps ----------
cd "${BASCULA_CURRENT_LINK}"
if [[ ! -d ".venv" ]]; then python3 -m venv --system-site-packages .venv; fi
source .venv/bin/activate
python -m pip install --upgrade --no-cache-dir pip wheel setuptools
python -m pip install --no-cache-dir pyserial pillow fastapi uvicorn[standard] pytesseract requests pyzbar
if [[ -f "requirements.txt" ]]; then python -m pip install --no-cache-dir -r requirements.txt || true; fi
deactivate

# ---------- Piper + say.sh ----------
apt-get install -y espeak-ng
if apt-cache policy piper 2>/dev/null | grep -q 'Candidate:'; then apt-get install -y piper; else python3 -m pip install --no-cache-dir piper-tts || true; fi
install -d -m 0755 /opt/piper/models
PIPER_ONNX="/opt/piper/models/es_ES-mls-medium.onnx"
PIPER_JSON="/opt/piper/models/es_ES-mls-medium.onnx.json"
if [[ ! -f "${PIPER_ONNX}" || ! -f "${PIPER_JSON}" ]]; then
  curl -L -o /tmp/es_ES-mls-medium.tar.gz https://github.com/rhasspy/piper/releases/download/v1.2.0/es_ES-mls-medium.tar.gz || true
  if [[ -f /tmp/es_ES-mls-medium.tar.gz ]]; then tar -xzf /tmp/es_ES-mls-medium.tar.gz -C /opt/piper/models; fi
  mv -f /opt/piper/models/*/*.onnx "${PIPER_ONNX}" 2>/dev/null || true
  mv -f /opt/piper/models/*/*.onnx.json "${PIPER_JSON}" 2>/dev/null || true
fi
cat > "${SAY_BIN}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
TEXT="${*:-}"
[ -z "$TEXT" ] && exit 0
PIPER_BIN="$(command -v piper || true)"
PIPER_ONNX="/opt/piper/models/es_ES-mls-medium.onnx"
PIPER_JSON="/opt/piper/models/es_ES-mls-medium.onnx.json"
if [[ -n "${PIPER_BIN}" && -f "${PIPER_ONNX}" && -f "${PIPER_JSON}" ]]; then
  echo -n "${TEXT}" | "${PIPER_BIN}" -m "${PIPER_ONNX}" -c "${PIPER_JSON}" --length-scale 0.97 --noise-scale 0.5 --noise-w 0.7 | aplay -q -r 22050 -f S16_LE -t raw -
else
  espeak-ng -v es -s 170 "${TEXT}" >/dev/null 2>&1 || true
fi
EOF
chmod 0755 "${SAY_BIN}"

# ---------- Mic test ----------
cat > "${MIC_TEST}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
CARD_DEVICE="${1:-plughw:1,0}"
DUR="${2:-5}"
RATE="${3:-16000}"
OUT="/tmp/mic_test.wav"
echo "[mic-test] Grabando ${DUR}s desde ${CARD_DEVICE} a ${RATE} Hz..."
arecord -D "${CARD_DEVICE}" -f S16_LE -c 1 -r "${RATE}" "${OUT}" -d "${DUR}"
echo "[mic-test] Reproduciendo ${OUT}..."
aplay "${OUT}"
EOF
chmod 0755 "${MIC_TEST}"

# ---------- IA: ASR (whisper.cpp) ----------
install -d -m 0755 /opt/whisper.cpp/models
if [[ ! -d /opt/whisper.cpp/.git ]]; then git clone https://github.com/ggerganov/whisper.cpp /opt/whisper.cpp; fi
make -C /opt/whisper.cpp -j"$(nproc)"
if [[ ! -f /opt/whisper.cpp/models/ggml-tiny-es.bin ]]; then
  curl -L -o /opt/whisper.cpp/models/ggml-tiny-es.bin https://ggml.ggerganov.com/whisper/ggml-tiny-es.bin
fi
cat > /usr/local/bin/hear.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
CARD_DEVICE="${1:-plughw:1,0}"
DUR="${2:-3}"
RATE="${3:-16000}"
MODEL="${4:-/opt/whisper.cpp/models/ggml-tiny-es.bin}"
TMP="/tmp/hear_$$.wav"
arecord -D "${CARD_DEVICE}" -f S16_LE -c 1 -r "${RATE}" "${TMP}" -d "${DUR}" >/dev/null 2>&1
/opt/whisper.cpp/main -m "${MODEL}" -f "${TMP}" -l es -otxt -of /tmp/hear_result >/dev/null 2>&1 || true
rm -f "${TMP}"
if [[ -f /tmp/hear_result.txt ]]; then sed 's/^[[:space:]]*//;s/[[:space:]]*$//' /tmp/hear_result.txt; else echo ""; fi
EOF
chmod 0755 /usr/local/bin/hear.sh

# ---------- IA: OCR (Tesseract + FastAPI) ----------
apt-get install -y tesseract-ocr tesseract-ocr-spa
install -d -m 0755 /opt/ocr-service
cat > /opt/ocr-service/app.py <<'PY'
import io
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse
from PIL import Image
import pytesseract
app = FastAPI(title="OCR Service", version="1.0")
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
systemctl daemon-reload
systemctl enable ocr-service.service
systemctl restart ocr-service.service || true

# ---------- IA: OCR robusto (PaddleOCR) ----------
source "${BASCULA_CURRENT_LINK}/.venv/bin/activate"
python -m pip install --no-cache-dir paddlepaddle==2.5.2 paddleocr==2.7.0.3 rapidocr-onnxruntime
deactivate

# ---------- IA: Vision-lite (TFLite) ----------
python3 -m pip install --no-cache-dir tflite-runtime==2.14.0 opencv-python-headless numpy
install -d -m 0755 /opt/vision-lite/models
cat > /opt/vision-lite/classify.py <<'PY'
import sys, numpy as np
import cv2
try:
    from tflite_runtime.interpreter import Interpreter
except Exception:
    from tensorflow.lite.python.interpreter import Interpreter
def softmax(x):
    e = np.exp(x - np.max(x)); return e / e.sum()
def main(img_path, model_path, label_path):
    labels = [l.strip() for l in open(label_path, 'r', encoding='utf-8')]
    interpreter = Interpreter(model_path=model_path); interpreter.allocate_tensors()
    in_d = interpreter.get_input_details()[0]; out_d = interpreter.get_output_details()[0]
    ih, iw = in_d['shape'][1], in_d['shape'][2]
    import numpy as _np
    img = cv2.imread(img_path); 
    if img is None: print("ERROR: no image", file=sys.stderr); sys.exit(2)
    x = cv2.resize(img, (iw, ih)); x = _np.expand_dims(x, 0).astype(_np.uint8 if in_d['dtype']==_np.uint8 else _np.float32)
    if x.dtype==_np.float32: x = x/255.0
    interpreter.set_tensor(in_d['index'], x); interpreter.invoke()
    y = interpreter.get_tensor(out_d['index'])[0]; y = y.flatten() if y.ndim>1 else y
    probs = softmax(y.astype(_np.float32)); top = probs.argsort()[-3:][::-1]
    for i in top: print(f"{labels[i]} {probs[i]:.3f}")
if __name__ == "__main__":
    if len(sys.argv)<4: print("Usage: python classify.py <image> <model.tflite> <labels.txt>"); sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
PY

# ---------- WiFi AP Fallback (NetworkManager) ----------
log "Instalando fallback WiFi AP (NetworkManager, copiando dispatcher desde el repo)..."
REPO_ROOT="${BASCULA_CURRENT_LINK}"
SRC_DISPATCH="${REPO_ROOT}/scripts/nm-dispatcher/90-bascula-ap-fallback"

install -d -m 0755 /etc/NetworkManager/dispatcher.d
if [[ -f "${SRC_DISPATCH}" ]]; then
  install -m 0755 "${SRC_DISPATCH}" /etc/NetworkManager/dispatcher.d/90-bascula-ap-fallback
  log "Dispatcher instalado."
else
  warn "No se encontró ${SRC_DISPATCH}. Sube ese archivo al repo."
fi

# Crear/actualizar conexión AP de NM
set +e
nmcli connection show "${AP_NAME}" >/dev/null 2>&1
EXISTS=$?
set -e

if [[ ${EXISTS} -ne 0 ]]; then
  log "Creando conexión AP ${AP_NAME} (SSID=${AP_SSID}) en ${AP_IFACE}"
  nmcli connection add type wifi ifname "${AP_IFACE}" con-name "${AP_NAME}" autoconnect no ssid "${AP_SSID}"
else
  log "Actualizando conexión AP existente ${AP_NAME}"
  nmcli connection modify "${AP_NAME}" 802-11-wireless.ssid "${AP_SSID}"
fi
nmcli connection modify "${AP_NAME}" 802-11-wireless.mode ap 802-11-wireless.band bg ipv4.method shared
nmcli connection modify "${AP_NAME}" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "${AP_PASS}"
nmcli connection modify "${AP_NAME}" connection.autoconnect no

# ---------- Habilitar servicios mini-web y UI ----------
for svc in bascula-web.service bascula-miniweb.service bascula-config.service; do
  if systemctl list-unit-files | grep -q "^${svc}\b"; then
    systemctl enable "$svc" || true
    systemctl restart "$svc" || true
  fi
done

# ---------- /run (tmpfiles) para heartbeat ----------
cat > "${TMPFILES}" <<EOF
d /run/bascula 0755 ${TARGET_USER} ${TARGET_GROUP} -
f /run/bascula.alive 0666 ${TARGET_USER} ${TARGET_GROUP} -
EOF
systemd-tmpfiles --create "${TMPFILES}" || true

# ---------- X session (kiosco) ----------
cat > "${XSESSION}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
export DISPLAY=:0
xset s off || true
xset -dpms || true
xset s noblank || true
unclutter -idle 0 -root &
if [[ -L "/opt/bascula/current" || -d "/opt/bascula/current" ]]; then
  cd /opt/bascula/current || true
fi
if [[ -f ".venv/bin/activate" ]]; then
  source ".venv/bin/activate"
fi
python3 - <<'PY' || true
import os, tkinter as tk
print("DISPLAY =", os.environ.get("DISPLAY"))
try:
    root = tk.Tk(); root.after(50, root.destroy); root.mainloop()
    print("TK_MIN_OK")
except Exception as e:
    print("TK_MIN_FAIL:", repr(e))
PY
if [[ -x "scripts/run-ui.sh" ]]; then
  exec scripts/run-ui.sh
fi
if python3 - <<'PY'
import importlib, sys
sys.path.insert(0, '/opt/bascula/current')
importlib.import_module('bascula.ui.app')
PY
then
  exec python3 -m bascula.ui.app
else
  exec python3 -m bascula.ui.recovery_ui
fi
EOF
chmod 0755 "${XSESSION}"

# ---------- Servicio app ----------
cat > "${SERVICE}" <<EOF
[Unit]
Description=Bascula Digital Pro Main Application (X on tty1)
After=network-online.target
Wants=network-online.target
[Service]
Type=simple
User=${TARGET_USER}
Group=${TARGET_GROUP}
WorkingDirectory=/opt/bascula/current
Environment=PYTHONPATH=/opt/bascula/current
RuntimeDirectory=bascula
RuntimeDirectoryMode=0755
Environment=BASCULA_RUNTIME_DIR=/run/bascula
ExecStart=/usr/bin/xinit ${XSESSION} -- :0 vt1 -nolisten tcp
Restart=on-failure
RestartSec=3
[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable bascula-app.service
systemctl start bascula-app.service || true

# ---------- Doctor: comprobaciones rápidas ----------
log "Comprobaciones post-instalación (doctor rápido)"
VENV_PY="${BASCULA_CURRENT_LINK}/.venv/bin/python"

# pyzbar + libzbar
if ldconfig -p 2>/dev/null | grep -q "zbar"; then
  log "libzbar: OK"
else
  warn "libzbar: NO ENCONTRADO (instala libzbar0)"
fi
PYZBAR_OUT="$(${VENV_PY} - <<'PY' 2>/dev/null || true
try:
    import pyzbar.pyzbar as _z
    import PIL
    print('OK')
except Exception as e:
    print('ERR:', e)
PY
)"
if echo "${PYZBAR_OUT}" | grep -q '^OK'; then
  log "pyzbar+Pillow: OK"
else
  warn "pyzbar+Pillow: FALLO -> ${PYZBAR_OUT}"
fi

# Picamera2 import
PIC_OUT="$(${VENV_PY} - <<'PY' 2>/dev/null || true
try:
    from picamera2 import Picamera2
    print('OK')
except Exception as e:
    print('ERR:', e)
PY
)"
if echo "${PIC_OUT}" | grep -q '^OK'; then
  log "Picamera2: OK"
else
  warn "Picamera2: FALLO -> ${PIC_OUT}"
fi

# OCR service activo + escucha puerto
if systemctl is-active --quiet ocr-service.service; then
  log "ocr-service: activo"
else
  warn "ocr-service: inactivo"
fi
HTTP_CODE="$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8078/ || echo 000)"
if [[ "${HTTP_CODE}" != "000" ]]; then
  log "ocr-service HTTP: responde (código ${HTTP_CODE})"
else
  warn "ocr-service HTTP: sin respuesta en 127.0.0.1:8078"
fi

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo "----------------------------------------------------"
echo "Instalación completada."
echo "Logs: /var/log/bascula"
echo "Release activa (symlink): ${BASCULA_CURRENT_LINK}"
echo "Mini-web panel: http://${IP:-<IP>}:8080/ (en AP suele ser http://10.42.0.1:8080)"
echo "ASR: hear.sh | OCR: http://127.0.0.1:8078/ocr"
echo "AP (NM): SSID=${AP_SSID} PASS=${AP_PASS} IFACE=${AP_IFACE} perfil=${AP_NAME}"
echo "Reinicia para aplicar overlays de I2S/KMS: sudo reboot"

#!/usr/bin/env bash
set -euo pipefail
#
# install-all.sh — Bascula-Cam (Raspberry Pi 5 - 4GB)
# - Preparado para Pi 5 (Bookworm 64-bit)
# - Cámara: libcamera0.5 + rpicam-apps + python3-picamera2
# - Voz: Piper (español) con fallback a espeak-ng
# - Audio I2S: MAX98357A (i2s-mmap + hifiberry-dac)
# - UI: Xorg mínimo + KMS + kiosco en tty1
# - OTA: /opt/bascula/{releases,current}
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

HDMI_W="${HDMI_W:-800}"
HDMI_H="${HDMI_H:-480}"
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

log "Actualizando índices APT…"
apt-get update -y

# ---------- Paquetes base ----------
PKGS_CORE=(
  git curl ca-certificates
  python3 python3-venv python3-pip python3-tk
  x11-xserver-utils xserver-xorg xinit openbox
  unclutter fonts-dejavu
  libjpeg-dev zlib1g-dev libpng-dev
  alsa-utils sox ffmpeg
  network-manager
  sqlite3
)
apt-get install -y "${PKGS_CORE[@]}"

# ---------- Limpieza libcamera antigua y preparación Pi 5 ----------
log "Liberando holds y limpiando libcamera antiguos…"
for p in libcamera0 libcamera-ipa libcamera-apps libcamera0.5 rpicam-apps python3-picamera2; do
  apt-mark unhold "$p" 2>/dev/null || true
done

# Remueve serie antigua si quedase algo
if dpkg -l | grep -q "^ii.*libcamera0 "; then
  apt-get remove --purge -y libcamera0 || true
fi
apt-get autoremove -y || true
apt-get autoclean -y || true

# ---------- Cámara (Pi 5: rama moderna 0.5) ----------
log "Instalando cámara (libcamera0.5 + rpicam-apps + python3-picamera2)…"
apt-get install -y --no-install-recommends libcamera-ipa libcamera0.5 || {
  err "Fallo instalando libcamera 0.5/ipa"; exit 1; }
# rpicam-apps preferido (si falta, intenta libcamera-apps)
if ! apt-get install -y rpicam-apps; then
  warn "rpicam-apps no disponible; usando libcamera-apps"
  apt-get install -y libcamera-apps
fi
apt-get install -y python3-picamera2

# Verificación import Picamera2 (puede requerir reinicio para funcionar la cámara real)
if python3 - <<'PY' 2>/dev/null; then
  from picamera2 import Picamera2
  print("Picamera2 OK")
PY
then
  log "Picamera2 importado correctamente."
else
  warn "Picamera2 instalado, el import falló (normal sin entorno completo). Seguir."
fi

# ---------- Configuración de UART (opcional, no interfiere) ----------
log "Habilitando UART…"
if [[ -f "${CONF}" ]] && ! grep -q "^enable_uart=1" "${CONF}"; then
  echo "enable_uart=1" >> "${CONF}"
  log "UART habilitado en ${CONF}"
fi
if [[ -f "${BOOTDIR}/cmdline.txt" ]]; then
  sed -i 's/console=serial0,115200 //g' "${BOOTDIR}/cmdline.txt" || true
fi
if command -v raspi-config >/dev/null 2>&1; then
  raspi-config nonint do_serial 0 || true
fi

# ---------- HDMI/KMS y GPU ----------
log "Aplicando configuración HDMI/KMS y GPU en ${CONF}…"
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
    echo "dtparam=audio=off        # desactiva audio analógico para liberar I2S"
    echo "dtoverlay=i2s-mmap       # habilita bus I2S"
    echo "dtoverlay=hifiberry-dac  # MAX98357A compatible"
  } >> "${CONF}"
else
  warn "No se encontró ${CONF}. Saltando ajustes HDMI/KMS/I2S."
fi

# ---------- Xwrapper (para permitir X desde servicio) ----------
log "Configurando ${XWRAPPER}…"
install -d -m 0755 /etc/X11
cat > "${XWRAPPER}" <<'EOF'
allowed_users=anybody
needs_root_rights=yes
EOF

# ---------- OTA: estructura releases/current ----------
log "Configurando estructura OTA en ${BASCULA_ROOT}…"
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
log "Configurando entorno virtual en ${BASCULA_CURRENT_LINK}…"
if [[ -d "${BASCULA_CURRENT_LINK}" ]]; then
  cd "${BASCULA_CURRENT_LINK}"
  if [[ ! -d ".venv" ]]; then
    python3 -m venv --system-site-packages .venv
  fi
  # shellcheck disable=SC1091
  source .venv/bin/activate
  python -m pip install --upgrade --no-cache-dir pip wheel setuptools

  # Paquetes base (añade aquí los que quieras optimizados para Pi 5)
  # NOTA: si usas OpenCV con GUI, puedes instalar 'opencv-python'; si no, 'opencv-python-headless'
  python -m pip install --no-cache-dir pyserial pillow
  if [[ -f "requirements.txt" ]]; then
    python -m pip install --no-cache-dir -r requirements.txt || true
  fi
  deactivate
else
  err "Directorio ${BASCULA_CURRENT_LINK} no encontrado."
  exit 1
fi

# ---------- Piper TTS (con fallback a espeak) ----------
log "Instalando motor de voz: Piper (preferente) + espeak-ng (fallback)…"
# 1) espeak-ng (fallback seguro)
apt-get install -y espeak-ng

# 2) piper: intenta vía APT si existe, si no, por pip
if apt-cache policy piper 2>/dev/null | grep -q 'Candidate:'; then
  apt-get install -y piper
else
  # Vía pip (instala binario 'piper')
  python3 -m pip install --upgrade --no-cache-dir piper-tts || {
    warn "Instalación de piper-tts vía pip falló; se usará espeak-ng como fallback."
  }
fi

# 3) Modelo español para Piper
PIPER_DIR="/opt/piper"
PIPER_MODELS="${PIPER_DIR}/models"
PIPER_BIN="$(command -v piper || true)"
install -d -m 0755 "${PIPER_MODELS}"

# Descarga de un modelo español estable (medium) si no existe
# Fuente: https://github.com/rhasspy/piper/releases  (en tiempo de ejecución con Internet)
# Usamos es_ES-mls-medium ya que es una voz neutra y ligera
PIPER_VOICE_BASE="es_ES-mls-medium"
PIPER_ONNX="${PIPER_MODELS}/${PIPER_VOICE_BASE}.onnx"
PIPER_JSON="${PIPER_MODELS}/${PIPER_VOICE_BASE}.onnx.json"

download_piper_voice() {
  local base_url="https://github.com/rhasspy/piper/releases/download/v1.2.0"
  local tar_name="${PIPER_VOICE_BASE}.tar.gz"
  local url="${base_url}/${tar_name}"
  local tmp="/tmp/${tar_name}"
  if [[ -f "${PIPER_ONNX}" && -f "${PIPER_JSON}" ]]; then
    log "Voz Piper ya presente: ${PIPER_VOICE_BASE}"
    return 0
  fi
  log "Descargando voz Piper (${PIPER_VOICE_BASE})…"
  if curl -L --fail -o "${tmp}" "${url}"; then
    tar -xzf "${tmp}" -C "${PIPER_MODELS}"
    # Algunos tar incluyen carpeta; reubicar si es necesario
    local found_onnx
    found_onnx="$(find "${PIPER_MODELS}" -maxdepth 2 -name '*.onnx' | head -n1 || true)"
    local found_json
    found_json="$(find "${PIPER_MODELS}" -maxdepth 2 -name '*.onnx.json' | head -n1 || true)"
    if [[ -n "${found_onnx}" && -n "${found_json}" ]]; then
      mv -f "${found_onnx}" "${PIPER_ONNX}" || true
      mv -f "${found_json}" "${PIPER_JSON}" || true
      log "Voz Piper instalada en ${PIPER_MODELS}"
      rm -f "${tmp}"
      return 0
    else
      warn "No se encontraron ficheros ONNX/JSON tras descomprimir."
      return 1
    fi
  else
    warn "No se pudo descargar la voz Piper (sin Internet?)."
    return 1
  fi
}

if [[ -n "${PIPER_BIN}" ]]; then
  download_piper_voice || warn "Continuando con espeak-ng como fallback si Piper no dispone de voz."
else
  warn "Piper no está instalado (binario ausente). Usaremos espeak-ng."
fi

# Wrapper de voz unificado
SAY_BIN="/usr/local/bin/say.sh"
log "Creando ${SAY_BIN}…"
cat > "${SAY_BIN}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
TEXT="${*:-}"
if [[ -z "${TEXT}" ]]; then
  exit 0
fi
PIPER_BIN="$(command -v piper || true)"
PIPER_ONNX="/opt/piper/models/es_ES-mls-medium.onnx"
PIPER_JSON="/opt/piper/models/es_ES-mls-medium.onnx.json"
if [[ -n "${PIPER_BIN}" && -f "${PIPER_ONNX}" && -f "${PIPER_JSON}" ]]; then
  echo -n "${TEXT}" | "${PIPER_BIN}" -m "${PIPER_ONNX}" -c "${PIPER_JSON}" --length-scale 0.97 --noise-scale 0.5 --noise-w 0.7 | aplay -q -r 22050 -f S16_LE -t raw -
else
  # Fallback: espeak-ng (rápido)
  espeak-ng -v es -s 170 "${TEXT}" >/dev/null 2>&1 || true
fi
EOF
chmod 0755 "${SAY_BIN}"
chown root:root "${SAY_BIN}"

# ---------- /run (tmpfiles) para heartbeat ----------
log "Creando ${TMPFILES}…"
cat > "${TMPFILES}" <<EOF
# /run/bascula para heartbeat
d /run/bascula 0755 ${TARGET_USER} ${TARGET_GROUP} -
# Si la app usa /run/bascula.alive directamente
f /run/bascula.alive 0666 ${TARGET_USER} ${TARGET_GROUP} -
EOF
systemd-tmpfiles --create "${TMPFILES}" || true

# ---------- X session (kiosco) ----------
log "Escribiendo ${XSESSION}…"
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

# Preflight mínimo de GUI/Tk
python3 - <<'PY' || true
import os, tkinter as tk
print("DISPLAY =", os.environ.get("DISPLAY"))
try:
    root = tk.Tk(); root.after(50, root.destroy); root.mainloop()
    print("TK_MIN_OK")
except Exception as e:
    print("TK_MIN_FAIL:", repr(e))
PY

# Lanzador preferente
if [[ -x "scripts/run-ui.sh" ]]; then
  exec scripts/run-ui.sh
fi

# Fallback por módulos
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
chown root:root "${XSESSION}"

# ---------- Servicio systemd ----------
log "Creando servicio ${SERVICE}…"
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
if systemctl start bascula-app.service && systemctl is-active --quiet bascula-app.service; then
  log "Servicio bascula-app.service activo."
else
  err "Servicio bascula-app.service no se inició. Revisa: systemctl status bascula-app.service"
fi

# ---------- Información final ----------
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo "----------------------------------------------------"
echo "Instalación completada."
echo "Logs: /var/log/bascula"
echo "Config persistente (si OTA): ${TARGET_HOME}/.bascula/config.json"
echo "Release activa (symlink): ${BASCULA_CURRENT_LINK}"
echo "URL mini-web (si tu build la incluye): http://${IP:-<IP>}:8080/"
echo "Voz: prueba con -> say.sh 'Hola Dani, la instalación ha finalizado.'"
echo "Importante: reinicia para aplicar overlays de I2S/KMS: sudo reboot"

#!/usr/bin/env bash
set -euo pipefail
#
# install-core.sh — Instala el sistema base, la UI y los servicios esenciales.
# SU OBJETIVO ES LA MÁXIMA FIABILIDAD.
#

log()  { printf "\033[1;34m[core]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }
err()  { printf "\033[1;31m[ERR ]\033[0m %s\n" "$*"; }

require_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    err "Ejecuta con sudo: sudo ./install-core.sh"
    exit 1
  fi
}
require_root

# --- Configuración ---
TARGET_USER="${TARGET_USER:-${SUDO_USER:-pi}}"
TARGET_GROUP="$(id -gn "$TARGET_USER")"
BASCULA_ROOT="/opt/bascula"
BASCULA_CURRENT_LINK="${BASCULA_ROOT}/current"
if [[ -d /boot/firmware ]]; then BOOTDIR="/boot/firmware"; else BOOTDIR="/boot"; fi
CONF="${BOOTDIR}/config.txt"

if [[ -L "${BASCULA_CURRENT_LINK}" ]]; then
  warn "La instalación principal ya existe. Saliendo."
  exit 0
fi

log "Usuario objetivo: $TARGET_USER ($TARGET_GROUP)"
apt-get update -y

# --- 1. PAQUETES DEL SISTEMA ---
log "Instalando paquetes base del sistema..."
apt-get install -y git curl ca-certificates build-essential cmake pkg-config \
  python3 python3-venv python3-pip python3-tk python3-serial \
  x11-xserver-utils xserver-xorg xinit openbox \
  unclutter fonts-dejavu libjpeg-dev zlib1g-dev libpng-dev \
  alsa-utils sox ffmpeg libzbar0 gpiod python3-rpi.gpio \
  network-manager sqlite3 tesseract-ocr tesseract-ocr-spa espeak-ng

# --- 2. CÁMARA Y HARDWARE ---
log "Configurando cámara y hardware (config.txt)..."
apt-get install -y --reinstall python3-picamera2 || true
# UART y Línea de Comandos
if ! grep -q "^enable_uart=1" "${CONF}"; then echo "enable_uart=1" >> "${CONF}"; fi
if [[ -f "${BOOTDIR}/cmdline.txt" ]]; then sed -i 's/console=serial0,115200 //g' "${BOOTDIR}/cmdline.txt"; fi
# HDMI, Audio y PWM
sed -i '/^hdmi_force_hotplug=/d;/^hdmi_group=/d;/^hdmi_mode=/d;/^hdmi_cvt=/d;/^dtoverlay=vc4-/d' "${CONF}"
{
  echo -e "\n#--- Bascula-Cam Core ---"
  echo "hdmi_force_hotplug=1"
  echo "hdmi_group=2"
  echo "hdmi_mode=87"
  echo "hdmi_cvt=1024 600 60 3 0 0 0"
  echo "dtoverlay=vc4-kms-v3d"
} >> "${CONF}"
if ! grep -q '^dtoverlay=pwm-2chan' "${CONF}"; then
  echo "dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4" >> "${CONF}"
  log "Overlay PWM añadido a ${CONF}"
fi
usermod -aG dialout,video,render "${TARGET_USER}" || true

# --- 3. CLONACIÓN DEL REPOSITORIO ---
log "Clonando el repositorio de la aplicación..."
install -d -m 0755 "${BASCULA_ROOT}/releases"
DEST="${BASCULA_ROOT}/releases/v1"
if ! git clone https://github.com/DanielGTdiabetes/bascula-cam.git "${DEST}"; then
  err "La clonación del repositorio falló."
  exit 1
fi
ln -s "${DEST}" "${BASCULA_CURRENT_LINK}"

# --- 4. ENTORNO VIRTUAL DE PYTHON (VENV) ---
log "Creando entorno Python 100% aislado..."
cd "${BASCULA_CURRENT_LINK}"
if [[ ! -d ".venv" ]]; then python3 -m venv .venv; fi
VENV_PY="${BASCULA_CURRENT_LINK}/.venv/bin/python"
"${VENV_PY}" -m pip install --upgrade pip wheel
log "Instalando dependencias de Python..."
"${VENV_PY}" -m pip install \
  "numpy==1.26.4" pyserial pillow "Flask>=2.2" fastapi "uvicorn[standard]" \
  pytesseract requests pyzbar "pytz>=2024.1" "opencv-python-headless<4.9"

# --- 5. Voces de Piper (Función Esencial) ---
log "Instalando programa y voces de Piper TTS..."
apt-get install -y piper || "${VENV_PY}" -m pip install piper-tts || warn "No se pudo instalar el programa Piper."
PIPER_VOICE="es_ES-mls_10246-medium"
PIPER_ONNX="/opt/piper/models/${PIPER_VOICE}.onnx"
if [[ ! -f "${PIPER_ONNX}" ]]; then
  install -d -m 0755 /opt/piper/models
  VOICE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/main/es/${PIPER_VOICE}.tar.gz"
  if curl -fL --retry 2 -m 30 -o "/tmp/piper.tar.gz" "${VOICE_URL}"; then
    tar -xzf "/tmp/piper.tar.gz" -C /opt/piper/models/
    log "Modelo de voz de Piper instalado."
  else
    warn "La descarga del modelo de voz de Piper falló."
  fi
fi

# --- 6. SERVICIOS Y PERMISOS FINALES ---
log "Configurando servicios systemd..."
# (Aquí irían los archivos de servicio copiados desde el repo si los tienes, o creados con `cat`)
# ... (Creación de ocr-service.service, bascula-web.service, bascula-app.service) ...
systemctl daemon-reload
# Iniciar y verificar servicios
log "Iniciando y verificando servicios web..."
systemctl enable --now ocr-service.service || true
sleep 2
if ! curl -fs http://127.0.0.1:8078/ >/dev/null 2>&1; then warn "Servicio OCR no responde."; fi
systemctl enable --now bascula-web.service || true
sleep 2
if ! curl -fs http://127.0.0.1:8080/ >/dev/null 2>&1; then warn "Servicio Mini-Web no responde."; fi
systemctl enable bascula-app.service || true

log "Asegurando permisos finales para el usuario ${TARGET_USER}..."
chown -R "${TARGET_USER}:${TARGET_GROUP}" "${BASCULA_ROOT}"
install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_GROUP}" /var/log/bascula

# --- 7. FINALIZACIÓN ---
log "Instalación principal completada."
echo "----------------------------------------------------"
echo "REINICIO REQUERIDO para aplicar cambios de hardware."
echo "Ejecuta: sudo reboot"
echo ""
echo "Después de reiniciar, ejecuta 'sudo ./install-ai-extras.sh' para las funciones de IA."
echo "----------------------------------------------------"

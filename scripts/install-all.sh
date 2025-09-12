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
AP_PASS_RAW="${AP_PASS:-bascula1234}"
AP_IFACE="${AP_IFACE:-wlan0}"
AP_NAME="${AP_NAME:-BasculaAP}"

# Validar clave WPA2-PSK (8-63 ASCII). Si no es válida, generar una segura por defecto.
_len=${#AP_PASS_RAW}
if [[ ${_len} -lt 8 || ${_len} -gt 63 ]]; then
  warn "AP_PASS inválida (longitud ${_len}). Usando valor por defecto seguro."
  AP_PASS="bascula1234"
else
  AP_PASS="${AP_PASS_RAW}"
fi
unset _len AP_PASS_RAW

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
# Opcional: actualización completa y firmware (set RUN_FULL_UPGRADE=1, RUN_RPI_UPDATE=1)
if [[ "${RUN_FULL_UPGRADE:-0}" = "1" ]]; then
  apt-get full-upgrade -y || true
fi
if [[ "${RUN_RPI_UPDATE:-0}" = "1" ]] && command -v rpi-update >/dev/null 2>&1; then
  SKIP_WARNING=1 rpi-update || true
fi

# ---------- Paquetes base ----------
apt-get install -y git curl ca-certificates build-essential cmake pkg-config \
  python3 python3-venv python3-pip python3-tk \
  x11-xserver-utils xserver-xorg xinit openbox \
  unclutter fonts-dejavu \
  libjpeg-dev zlib1g-dev libpng-dev \
  alsa-utils sox ffmpeg \
  libzbar0 gpiod python3-rpi.gpio \
  network-manager sqlite3

# Comprobar conectividad básica para operaciones con pip/descargas
NET_OK=0
if command -v curl >/dev/null 2>&1; then
  if curl -fsI -m 4 https://pypi.org/simple >/dev/null 2>&1; then NET_OK=1; fi
fi
if [[ "${NET_OK}" = "1" ]]; then
  log "Conectividad PyPI: OK"
else
  warn "Conectividad PyPI: NO (algunos pasos pip/descargas se omitirán)"
fi

# Paquete offline opcional (USB/BOOT): /boot/bascula-offline o BASCULA_OFFLINE_DIR
OFFLINE_DIR="${BASCULA_OFFLINE_DIR:-/boot/bascula-offline}"
if [[ -d "${OFFLINE_DIR}" ]]; then
  log "Paquete offline detectado en: ${OFFLINE_DIR}"
fi

# Evitar compilación de PyMuPDF desde pip cuando sea posible
if apt-cache policy python3-pymupdf 2>/dev/null | grep -q 'Candidate:'; then
  apt-get install -y python3-pymupdf || true
else
  warn "python3-pymupdf no disponible en APT; si se necesita, pip podría compilarlo."
fi

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
# Liberar UART para usos externos: desactivar BT sobre UART si aplica
if [[ -f "${CONF}" ]] && ! grep -q "^dtoverlay=disable-bt" "${CONF}"; then echo "dtoverlay=disable-bt" >> "${CONF}"; fi
systemctl disable --now hciuart 2>/dev/null || true

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
    echo "# X735: habilitar PWM fan en GPIO13 (PWM1)"
    sed -i '/^dtoverlay=pwm-2chan/d' "${CONF}" || true
    # Habilitar ambos canales por compatibilidad (PWM0 en GPIO12 y PWM1 en GPIO13)
    echo "dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4"
  } >> "${CONF}"
fi

# ---------- EEPROM: aumentar PSU_MAX_CURRENT para Pi 5 (X735) ----------
if command -v rpi-eeprom-config >/dev/null 2>&1; then
  TMP_EE="/tmp/eeconf_$$.txt"
  if rpi-eeprom-config > "${TMP_EE}" 2>/dev/null; then
    if grep -q '^PSU_MAX_CURRENT=' "${TMP_EE}"; then
      sed -i 's/^PSU_MAX_CURRENT=.*/PSU_MAX_CURRENT=5000/' "${TMP_EE}"
    else
      echo "PSU_MAX_CURRENT=5000" >> "${TMP_EE}"
    fi
    rpi-eeprom-config --apply "${TMP_EE}" || true
    rm -f "${TMP_EE}"
  fi
fi

# ---------- Xwrapper ----------
install -d -m 0755 /etc/X11
cat > "${XWRAPPER}" <<'EOF'
allowed_users=anybody
needs_root_rights=yes
EOF

# ---------- Polkit (NetworkManager sin sudo) ----------
install -d -m 0755 /etc/polkit-1
install -d -m 0755 /etc/polkit-1/rules.d
cat > /etc/polkit-1/rules.d/50-bascula-nm.rules <<EOF
polkit.addRule(function(action, subject) {
  if (subject.user == "${TARGET_USER}" || subject.isInGroup("${TARGET_GROUP}")) {
    if (action.id == "org.freedesktop.NetworkManager.settings.modify.system" ||
        action.id == "org.freedesktop.NetworkManager.network-control" ||
        action.id == "org.freedesktop.NetworkManager.enable-disable-wifi") {
      return polkit.Result.YES;
    }
  }
});
EOF
systemctl restart polkit || true
systemctl restart NetworkManager || true

# Detectar interfaz Wi‑Fi si AP_IFACE no existe o no es Wi‑Fi gestionada
if ! nmcli -t -f DEVICE,TYPE device status 2>/dev/null | awk -F: -v d="${AP_IFACE}" '($1==d && $2=="wifi"){f=1} END{exit f?0:1}'; then
  _WDEV="$(nmcli -t -f DEVICE,TYPE,STATE device status 2>/dev/null | awk -F: '$2=="wifi"{print $1; exit}')"
  if [[ -z "${_WDEV}" ]] && command -v iw >/dev/null 2>&1; then
    _WDEV="$(iw dev 2>/dev/null | awk '/Interface/{print $2; exit}')"
  fi
  if [[ -n "${_WDEV}" ]]; then
    AP_IFACE="${_WDEV}"
    log "Interfaz Wi‑Fi detectada: ${AP_IFACE}"
  else
    warn "No se encontró interfaz Wi‑Fi gestionada por NM; usando ${AP_IFACE}"
  fi
  unset _WDEV
fi

# ---------- Pre‑Net: asegurar conectividad a Internet (Wi‑Fi/Ethernet) antes de OTA ----------
# Permitir pasar credenciales por env o archivo /boot/bascula-wifi.json
WIFI_SSID="${WIFI_SSID:-}"
WIFI_PASS="${WIFI_PASS:-}"
WIFI_HIDDEN="${WIFI_HIDDEN:-0}"
WIFI_COUNTRY="${WIFI_COUNTRY:-}"

# Cargar de JSON si no se proporcionó por env
if [[ -z "${WIFI_SSID}" && -f "/boot/bascula-wifi.json" ]]; then
  readarray -t _WF < <(python3 - <<'PY' 2>/dev/null || true
import json,sys
try:
    with open('/boot/bascula-wifi.json','r',encoding='utf-8') as f:
        d=json.load(f)
    print(d.get('ssid',''))
    print(d.get('psk',''))
    print('1' if d.get('hidden') else '0')
    print(d.get('country',''))
except Exception:
    pass
PY
)
  WIFI_SSID="${_WF[0]:-}"
  WIFI_PASS="${_WF[1]:-}"
  WIFI_HIDDEN="${_WF[2]:-0}"
  WIFI_COUNTRY="${_WF[3]:-}"
  unset _WF
fi

# Si aún no hay credenciales, intentar desde wpa_supplicant.conf
if [[ -z "${WIFI_SSID}" ]]; then
  for WCONF in "/boot/wpa_supplicant.conf" "/boot/firmware/wpa_supplicant.conf"; do
    if [[ -f "${WCONF}" ]]; then
      readarray -t _WF < <(python3 - "${WCONF}" <<'PY' 2>/dev/null || true
import sys, re
ssid = psk = None
scan_ssid = '0'
country = ''
path = sys.argv[1]
try:
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = [l.strip() for l in f]
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith('country=') and not country:
            country = ln.split('=',1)[1].strip().strip('"')
        if ln.startswith('network={'):
            i += 1
            ssid = psk = None
            scan_ssid = '0'
            while i < len(lines) and not lines[i].startswith('}'):
                k, _, v = lines[i].partition('=')
                k = k.strip(); v = v.strip()
                if k == 'ssid': ssid = v
                elif k == 'psk': psk = v
                elif k == 'scan_ssid': scan_ssid = v
                i += 1
            # Al cerrar el bloque network, si hay SSID, salimos (tomamos el primero)
            if ssid:
                break
        i += 1
    def dq(x):
        if x is None: return ''
        x = x.strip()
        if len(x) >= 2 and x[0] == '"' and x[-1] == '"':
            return x[1:-1]
        return x
    print(dq(ssid))              # 0: SSID
    print(dq(psk))               # 1: PSK (vacío si abierta)
    print('1' if str(scan_ssid).strip() in ('1','true','True') else '0')  # 2: hidden
    print(country)               # 3: country
except Exception:
    pass
PY
)
      WIFI_SSID="${_WF[0]:-}"
      WIFI_PASS="${_WF[1]:-}"
      WIFI_HIDDEN="${_WF[2]:-0}"
      # Solo sobreescribir país si no venía por env/JSON
      if [[ -z "${WIFI_COUNTRY}" ]]; then WIFI_COUNTRY="${_WF[3]:-}"; fi
      unset _WF
      if [[ -n "${WIFI_SSID}" ]]; then
        log "Credenciales Wi‑Fi importadas desde ${WCONF} (SSID=${WIFI_SSID})"
        break
      fi
    fi
  done
fi

# Ajustar dominio regulatorio si se indicó
if [[ -n "${WIFI_COUNTRY}" ]] && command -v iw >/dev/null 2>&1; then
  iw reg set "${WIFI_COUNTRY}" 2>/dev/null || true
fi

# Funciones de conectividad
have_inet() { curl -fsI -m 4 https://deb.debian.org >/dev/null 2>&1 || curl -fsI -m 4 https://pypi.org/simple >/dev/null 2>&1; }
wifi_active() { nmcli -t -f TYPE,STATE connection show --active 2>/dev/null | grep -q '^wifi:activated$'; }
ap_active() { nmcli -t -f NAME,DEVICE connection show --active 2>/dev/null | grep -q "^${AP_NAME}:"; }

# Encender Wi‑Fi y desbloquear RF
rfkill unblock wifi 2>/dev/null || true
nmcli radio wifi on >/dev/null 2>&1 || true
nmcli device set "${AP_IFACE}" managed yes >/dev/null 2>&1 || true

# Bajar AP si está activo para permitir escaneo/asociación lo antes posible
if nmcli -t -f NAME,DEVICE connection show --active 2>/dev/null | grep -q "^${AP_NAME}:"; then
  nmcli connection down "${AP_NAME}" >/dev/null 2>&1 || true
fi

# Si hay credenciales, crear/levantar conexión normal antes de OTA
if [[ -n "${WIFI_SSID}" ]]; then
  # Forzar un rescan para detectar redes disponibles
  nmcli device wifi rescan ifname "${AP_IFACE}" >/dev/null 2>&1 || true
  nmcli -t -f NAME connection show | grep -qx "BasculaWiFi" || nmcli connection add type wifi ifname "${AP_IFACE}" con-name "BasculaWiFi" ssid "${WIFI_SSID}" || true
  # Asegurar SSID actualizado
  nmcli connection modify "BasculaWiFi" 802-11-wireless.ssid "${WIFI_SSID}" || true
  # Seguridad: WPA-PSK si hay clave; abierta si no
  if [[ -n "${WIFI_PASS}" ]]; then
    nmcli connection modify "BasculaWiFi" \
      802-11-wireless-security.key-mgmt wpa-psk \
      802-11-wireless-security.psk "${WIFI_PASS}" || true
  else
    nmcli connection modify "BasculaWiFi" \
      802-11-wireless-security.key-mgmt none || true
  fi
  nmcli connection modify "BasculaWiFi" 802-11-wireless.hidden "${WIFI_HIDDEN}" connection.autoconnect yes connection.autoconnect-priority 10 || true
fi

# Bajar AP si está activo para permitir escaneo/asociación
if ap_active; then nmcli connection down "${AP_NAME}" >/dev/null 2>&1 || true; fi

# Intentar hasta 6 veces: asociar Wi‑Fi (si se configuró) y comprobar Internet
NET_READY=0
for _i in 1 2 3 4 5 6; do
  if have_inet; then NET_READY=1; break; fi
  if [[ -n "${WIFI_SSID}" ]]; then
    nmcli device wifi rescan ifname "${AP_IFACE}" >/dev/null 2>&1 || true
    nmcli connection up "BasculaWiFi" ifname "${AP_IFACE}" >/dev/null 2>&1 || true
  fi
  sleep 4
done
if [[ ${NET_READY} -eq 1 ]]; then
  log "Conectividad previa a OTA: OK"
else
  warn "Sin Internet previo a OTA. Intentaré OTA con fallback local si existe."
fi

# ---------- OTA: releases/current (con fallback offline) ----------
install -d -m 0755 "${BASCULA_RELEASES_DIR}"
if [[ ! -e "${BASCULA_CURRENT_LINK}" ]]; then
  DEST="${BASCULA_RELEASES_DIR}/v1"

  # 1) Intento online (GitHub)
  if git ls-remote https://github.com/DanielGTdiabetes/bascula-cam.git >/dev/null 2>&1; then
    log "Clonando repositorio en ${DEST}…"
    git clone https://github.com/DanielGTdiabetes/bascula-cam.git "${DEST}"
    ln -s "${DEST}" "${BASCULA_CURRENT_LINK}"
  else
    # 2) Fallback offline: copiar desde un repo local
    # Permitir indicar la ruta vía BASCULA_SOURCE_DIR o autodetectar desde este script
    SRC_DIR="${BASCULA_SOURCE_DIR:-}"
    if [[ -z "${SRC_DIR}" ]]; then
      # Directorio del script y posible raíz del repo (scripts/..)
      _SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
      _CANDIDATE="$(cd "${_SCRIPT_DIR}/.." && pwd)"
      # Si es un repo git, tomar su raíz, si no, usar candidato tal cual
      if ROOT_GIT="$(git -C "${_CANDIDATE}" rev-parse --show-toplevel 2>/dev/null || true)" && [[ -n "${ROOT_GIT}" ]]; then
        SRC_DIR="${ROOT_GIT}"
      else
        SRC_DIR="${_CANDIDATE}"
      fi
      unset _SCRIPT_DIR _CANDIDATE ROOT_GIT
    fi

    # Validar que SRC_DIR parece el repo correcto
    if [[ -d "${SRC_DIR}" && -f "${SRC_DIR}/scripts/install-all.sh" && -d "${SRC_DIR}/bascula" ]]; then
      log "Sin acceso a GitHub. Usando copia local: ${SRC_DIR}"
      install -d -m 0755 "${DEST}"
      # Copiar excluyendo artefactos
      (
        cd "${SRC_DIR}"
        tar --exclude .git --exclude .venv --exclude __pycache__ --exclude '*.pyc' -cf - .
      ) | (
        tar -xf - -C "${DEST}"
      )
      ln -s "${DEST}" "${BASCULA_CURRENT_LINK}"
    else
      err "No hay acceso a GitHub y no se encontró un repo local válido."
      err "Opciones:"
      err "  - Conecta a Internet y reintenta"
      err "  - O define BASCULA_SOURCE_DIR con la ruta del repo y reintenta"
      err "  - O crea/ajusta manualmente ${BASCULA_CURRENT_LINK} -> ${DEST}"
      exit 1
    fi
  fi
fi
chown -R "${TARGET_USER}:${TARGET_GROUP}" "${BASCULA_ROOT}"
install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_GROUP}" /var/log/bascula

# ---------- VENV + Python deps ----------
cd "${BASCULA_CURRENT_LINK}"
if [[ ! -d ".venv" ]]; then python3 -m venv --system-site-packages .venv; fi
VENV_DIR="${BASCULA_CURRENT_LINK}/.venv"
VENV_PY="${VENV_DIR}/bin/python"
VENV_PIP="${VENV_DIR}/bin/pip"
# Prefer binary wheels to avoid slow native builds on Pi
export PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore PIP_PREFER_BINARY=1
# Usar piwheels por defecto en Raspberry Pi (si no viene definido)
export PIP_INDEX_URL="${PIP_INDEX_URL:-https://www.piwheels.org/simple}"
export PIP_EXTRA_INDEX_URL="${PIP_EXTRA_INDEX_URL:-https://pypi.org/simple}"
if [[ "${NET_OK}" = "1" ]]; then
  "${VENV_PY}" -m pip install -q --upgrade --no-cache-dir pip wheel setuptools || true
  "${VENV_PY}" -m pip install -q --no-cache-dir pyserial pillow fastapi "uvicorn[standard]" pytesseract requests pyzbar "pytz>=2024.1" || true
  # If requirements.txt exists, avoid forcing a PyMuPDF build if the apt package is available
  if [[ -f "requirements.txt" ]]; then
    SKIP_PYMUPDF=0
    if "${VENV_PY}" - <<'PY'
import importlib.util, sys
sys.exit(0 if importlib.util.find_spec("fitz") else 1)
PY
    then
      SKIP_PYMUPDF=1
    fi
    if [[ "${SKIP_PYMUPDF}" = "1" ]]; then
      TMP_REQ="/tmp/requirements.no-pymupdf.$$.txt"
      # Remove lines starting with (case-insensitive) 'pymupdf'
      if grep -qiE '^[[:space:]]*pymupdf\b' requirements.txt; then
        log "requirements.txt: omitiendo PyMuPDF (provisto por APT)"
      fi
      grep -viE '^[[:space:]]*pymupdf\b' requirements.txt > "${TMP_REQ}" || true
      "${VENV_PY}" -m pip install -q --no-cache-dir -r "${TMP_REQ}" || true
      rm -f "${TMP_REQ}" || true
    else
      "${VENV_PY}" -m pip install -q --no-cache-dir -r requirements.txt || true
    fi
  fi
  # Si pip instaló piper-tts, expone un binario 'piper' dentro del venv; enlazar si falta en PATH
  if [[ -x "${VENV_DIR}/bin/piper" ]] && ! command -v piper >/dev/null 2>&1; then
    ln -sf "${VENV_DIR}/bin/piper" /usr/local/bin/piper || true
  fi
else
  # Modo offline con wheels precompiladas si existen
  if [[ -d "${OFFLINE_DIR}/wheels" ]]; then
    log "Instalando dependencias del venv desde wheels offline (${OFFLINE_DIR}/wheels)"
    "${VENV_PY}" -m pip install --no-index --find-links "${OFFLINE_DIR}/wheels" wheel setuptools || true
    "${VENV_PY}" -m pip install --no-index --find-links "${OFFLINE_DIR}/wheels" pyserial pillow fastapi "uvicorn[standard]" pytesseract requests pyzbar "pytz>=2024.1" || true
    if [[ -f "${OFFLINE_DIR}/requirements.txt" ]]; then
      "${VENV_PY}" -m pip install --no-index --find-links "${OFFLINE_DIR}/wheels" -r "${OFFLINE_DIR}/requirements.txt" || true
    fi
    # Enlazar piper del venv si existe
    if [[ -x "${VENV_DIR}/bin/piper" ]] && ! command -v piper >/dev/null 2>&1; then
      ln -sf "${VENV_DIR}/bin/piper" /usr/local/bin/piper || true
    fi
  else
    warn "Sin red y sin wheels offline: saltando instalación de dependencias del venv"
  fi
fi

# ---------- X735 (v2.5/v3.0): servicios de ventilador PWM y gestión de energía ----------
install -d -m 0755 /opt
if [[ ! -d /opt/x735-script/.git ]]; then
  git clone https://github.com/geekworm-com/x735-script /opt/x735-script || true
fi
if [[ -d /opt/x735-script ]]; then
  cd /opt/x735-script || true
  chmod +x *.sh || true
  # En Pi 5 el pwmchip es 2 (no 0)
  sed -i 's/pwmchip0/pwmchip2/g' x735-fan.sh 2>/dev/null || true
  # Instalar servicios (fan y power). Fan requiere kernel >= 6.6.22
  ./install-fan-service.sh || true
  ./install-pwr-service.sh || true
  # Drop-in para retrasar inicio hasta que PWM esté disponible y evitar FAIL temprano
  install -d -m 0755 /etc/systemd/system/x735-fan.service.d
  cat > /etc/systemd/system/x735-fan.service.d/override.conf <<'EOF'
[Unit]
After=local-fs.target sysinit.target
ConditionPathExistsGlob=/sys/class/pwm/pwmchip*

[Service]
ExecStartPre=/bin/sh -c 'for i in $(seq 1 20); do for c in /sys/class/pwm/pwmchip2 /sys/class/pwm/pwmchip1 /sys/class/pwm/pwmchip0; do [ -d "$c" ] && exit 0; done; sleep 1; done; exit 0'
Restart=on-failure
RestartSec=5
EOF
  systemctl daemon-reload || true
  systemctl enable --now x735-fan.service 2>/dev/null || true
  # Comando de apagado seguro
  cp -f ./xSoft.sh /usr/local/bin/ 2>/dev/null || true
  if ! grep -q 'alias x735off=' "${TARGET_HOME}/.bashrc" 2>/dev/null; then
    echo 'alias x735off="sudo /usr/local/bin/xSoft.sh 0 20"' >> "${TARGET_HOME}/.bashrc"
    chown "${TARGET_USER}:${TARGET_GROUP}" "${TARGET_HOME}/.bashrc" || true
  fi
fi

# Asegurador post‑reboot para X735 (se encarga de instalar/ajustar fan/pwr cuando el PWM está disponible)
cat > /usr/local/sbin/x735-ensure.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
STAMP=/var/lib/x735-setup.done
LOG(){ printf "[x735] %s\n" "$*"; }

# Comprobar PWM disponible (Pi 5 usa pwmchip2)
PWMCHIP=
for c in /sys/class/pwm/pwmchip2 /sys/class/pwm/pwmchip1 /sys/class/pwm/pwmchip0; do
  if [[ -d "$c" ]]; then PWMCHIP="${c##*/}"; break; fi
done
if [[ -z "${PWMCHIP}" ]]; then
  LOG "PWM no disponible aún; reintentar tras próximo arranque"
  exit 0
fi

# Clonar/actualizar scripts
if [[ ! -d /opt/x735-script/.git ]]; then
  git clone https://github.com/geekworm-com/x735-script /opt/x735-script || true
fi
cd /opt/x735-script || exit 0
chmod +x *.sh || true

# Ajustar pwmchip en script de ventilador
sed -i "s/pwmchip[0-9]\+/$(printf %s "${PWMCHIP}")/g" x735-fan.sh 2>/dev/null || true

# Instalar servicios
./install-fan-service.sh || true
./install-pwr-service.sh || true

# Habilitar servicios
systemctl enable --now x735-fan.service 2>/dev/null || true
systemctl enable --now x735-pwr.service 2>/dev/null || true

touch "${STAMP}"
LOG "Instalación/ajuste X735 completado (pwmchip=${PWMCHIP})"
exit 0
EOF
chmod 0755 /usr/local/sbin/x735-ensure.sh
install -d -m 0755 /var/lib

cat > /etc/systemd/system/x735-ensure.service <<'EOF'
[Unit]
Description=Ensure X735 fan/power services installed and configured
After=multi-user.target local-fs.target
ConditionPathExists=!/var/lib/x735-setup.done

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/x735-ensure.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable x735-ensure.service || true

# ---------- Piper + say.sh ----------
apt-get install -y espeak-ng
# 1) Intento instalar piper por apt, si no, por pip
if apt-cache policy piper 2>/dev/null | grep -q 'Candidate:'; then
  apt-get install -y piper
else
  if [[ "${NET_OK}" = "1" ]]; then "${VENV_PY}" -m pip install -q --no-cache-dir piper-tts || true; else warn "Sin red: omitiendo instalación pip de piper-tts"; fi
fi

# 2) Si no quedó disponible el binario `piper`, descargar binario precompilado (fallback)
if ! command -v piper >/dev/null 2>&1; then
  # Fallback offline: binario aportado en bundle
  if [[ -d "${OFFLINE_DIR}" ]]; then
    # p. ej., ${OFFLINE_DIR}/piper/bin/piper o piper_linux_*.tar.gz
    if F_BIN_OFF="$(find "${OFFLINE_DIR}" -maxdepth 3 -type f -name 'piper' 2>/dev/null | head -n1)" && [[ -n "${F_BIN_OFF}" ]]; then
      install -d -m 0755 /opt/piper/bin
      cp -f "${F_BIN_OFF}" /opt/piper/bin/piper 2>/dev/null || true
      chmod +x /opt/piper/bin/piper 2>/dev/null || true
      ln -sf /opt/piper/bin/piper /usr/local/bin/piper 2>/dev/null || true
    fi
  fi
  ARCH="$(uname -m 2>/dev/null || echo unknown)"
  PIPER_BIN_URL=""
  case "${ARCH}" in
    aarch64) PIPER_BIN_URL="https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_aarch64.tar.gz" ;;
    armv7l)  PIPER_BIN_URL="https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_armv7l.tar.gz" ;;
    x86_64)  PIPER_BIN_URL="https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz" ;;
  esac
  if [[ -n "${PIPER_BIN_URL}" ]]; then
    install -d -m 0755 /opt/piper/bin
    TMP_TGZ="/tmp/piper_bin_$$.tgz"
    if curl -fL --retry 2 -m 20 -o "${TMP_TGZ}" "${PIPER_BIN_URL}" 2>/dev/null && tar -tzf "${TMP_TGZ}" >/dev/null 2>&1; then
      tar -xzf "${TMP_TGZ}" -C /opt/piper/bin || true
      rm -f "${TMP_TGZ}" || true
      # Intentar ubicar el binario extraído y hacerlo accesible
      F_BIN="$(find /opt/piper/bin -maxdepth 2 -type f -name 'piper' | head -n1)"
      if [[ -n "${F_BIN}" ]]; then
        chmod +x "${F_BIN}" || true
        ln -sf "${F_BIN}" /usr/local/bin/piper || true
      fi
    else
      warn "Descarga del binario Piper falló para ARCH=${ARCH}. Continuando con espeak-ng como fallback."
    fi
  else
    warn "Arquitectura ${ARCH} no soportada para binario precompilado de Piper."
  fi
fi

install -d -m 0755 /opt/piper/models

# Voz por defecto de Piper (puedes sobreescribir con PIPER_VOICE)
PIPER_VOICE="${PIPER_VOICE:-es_ES-mls-medium}"
PIPER_ONNX="/opt/piper/models/${PIPER_VOICE}.onnx"
PIPER_JSON="/opt/piper/models/${PIPER_VOICE}.onnx.json"
if [[ ! -f "${PIPER_ONNX}" || ! -f "${PIPER_JSON}" ]]; then
  PIPER_TGZ="/tmp/${PIPER_VOICE}.tar.gz"
  # Fallback offline: voz predescargada
  if [[ -f "${OFFLINE_DIR}/piper-voices/${PIPER_VOICE}.tar.gz" ]]; then
    cp -f "${OFFLINE_DIR}/piper-voices/${PIPER_VOICE}.tar.gz" "${PIPER_TGZ}" 2>/dev/null || true
  fi
  # Intentar varias URLs conocidas (GitHub release y Hugging Face)
  URLS=(
    "https://github.com/rhasspy/piper/releases/download/v1.2.0/${PIPER_VOICE}.tar.gz"
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/${PIPER_VOICE}.tar.gz"
    "https://huggingface.co/datasets/rhasspy/piper-voices/resolve/main/es/${PIPER_VOICE}.tar.gz"
  )
  if [[ ! -f "${PIPER_TGZ}" ]] || ! tar -tzf "${PIPER_TGZ}" >/dev/null 2>&1; then
    for U in "${URLS[@]}"; do
      rm -f "${PIPER_TGZ}"
      if curl -fL --retry 2 -m 30 -o "${PIPER_TGZ}" "${U}" 2>/dev/null && tar -tzf "${PIPER_TGZ}" >/dev/null 2>&1; then
        break
      fi
    done
  fi
  if [[ -f "${PIPER_TGZ}" ]] && tar -tzf "${PIPER_TGZ}" >/dev/null 2>&1; then
    tar -xzf "${PIPER_TGZ}" -C /opt/piper/models || true
    # Mover el modelo y su JSON a la ruta estándar
    F_ONNX="$(find /opt/piper/models -maxdepth 2 -type f -name '*.onnx' | head -n1)"
    F_JSON="$(find /opt/piper/models -maxdepth 2 -type f -name '*.onnx.json' | head -n1)"
    [[ -n "${F_ONNX}" ]] && mv -f "${F_ONNX}" "${PIPER_ONNX}" 2>/dev/null || true
    [[ -n "${F_JSON}" ]] && mv -f "${F_JSON}" "${PIPER_JSON}" 2>/dev/null || true
  else
    warn "No se pudo descargar la voz de Piper (${PIPER_VOICE}). Se usará espeak-ng como fallback."
  fi
fi
cat > "${SAY_BIN}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
TEXT="${*:-}"
[ -z "$TEXT" ] && exit 0

# 1) Localizar binario piper
if [[ -n "${PIPER_BIN:-}" && -x "${PIPER_BIN}" ]]; then
  BIN="${PIPER_BIN}"
else
  BIN="$(command -v piper || true)"
  if [[ -z "${BIN}" ]]; then
    # Fallback: binario del venv
    if [[ -x "/opt/bascula/current/.venv/bin/piper" ]]; then
      BIN="/opt/bascula/current/.venv/bin/piper"
    else
      # Fallback: binario descargado en /opt/piper/bin
      F_BIN="$(find /opt/piper/bin -maxdepth 2 -type f -name piper 2>/dev/null | head -n1 || true)"
      if [[ -n "${F_BIN}" ]]; then BIN="${F_BIN}"; fi
    fi
  fi
fi

# 2) Localizar modelo/config
VOICE="${PIPER_VOICE:-es_ES-mls-medium}"
MODEL="${PIPER_MODEL:-/opt/piper/models/${VOICE}.onnx}"
CONFIG="${PIPER_CONFIG:-/opt/piper/models/${VOICE}.onnx.json}"
if [[ ! -f "${MODEL}" ]]; then
  # Elegir el primer .onnx disponible (preferir 'es_')
  CAND="$(find /opt/piper/models -maxdepth 2 -type f -name '*.onnx' 2>/dev/null | grep -E '/es' | head -n1 || true)"
  [[ -z "${CAND}" ]] && CAND="$(find /opt/piper/models -maxdepth 2 -type f -name '*.onnx' 2>/dev/null | head -n1 || true)"
  [[ -n "${CAND}" ]] && MODEL="${CAND}"
fi
if [[ ! -f "${CONFIG}" ]]; then
  # Buscar .onnx.json o .json pareja del modelo
  base="${MODEL%.onnx}"
  if [[ -f "${base}.onnx.json" ]]; then CONFIG="${base}.onnx.json";
  elif [[ -f "${base}.json" ]]; then CONFIG="${base}.json";
  else
    CJSON="$(find /opt/piper/models -maxdepth 2 -type f \( -name '*.onnx.json' -o -name '*.json' \) 2>/dev/null | head -n1 || true)"
    [[ -n "${CJSON}" ]] && CONFIG="${CJSON}"
  fi
fi

# 3) Reproducir con Piper si es posible, si no espeak-ng
if [[ -n "${BIN}" && -x "${BIN}" && -f "${MODEL}" && -f "${CONFIG}" ]]; then
  echo -n "${TEXT}" | "${BIN}" -m "${MODEL}" -c "${CONFIG}" --length-scale 0.97 --noise-scale 0.5 --noise-w 0.7 | aplay -q -r 22050 -f S16_LE -t raw -
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
install -d -m 0755 /opt
if [[ -d /opt/whisper.cpp ]]; then
  if git -C /opt/whisper.cpp rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git -C /opt/whisper.cpp pull --ff-only || true
  else
    warn "/opt/whisper.cpp existe pero no es un repo git. Respaldando y reclonando."
    mv /opt/whisper.cpp "/opt/whisper.cpp.bak.$(date +%s)" || true
    git clone https://github.com/ggerganov/whisper.cpp /opt/whisper.cpp || true
  fi
else
  git clone https://github.com/ggerganov/whisper.cpp /opt/whisper.cpp || true
fi
install -d -m 0755 /opt/whisper.cpp/models
make -C /opt/whisper.cpp -j"$(nproc)" || true
if [[ ! -f /opt/whisper.cpp/models/ggml-tiny-es.bin ]]; then
  if [[ -f "${OFFLINE_DIR}/whisper/ggml-tiny-es.bin" ]]; then
    cp -f "${OFFLINE_DIR}/whisper/ggml-tiny-es.bin" /opt/whisper.cpp/models/ggml-tiny-es.bin || true
  else
    curl -L --retry 2 -m 40 -o /opt/whisper.cpp/models/ggml-tiny-es.bin https://ggml.ggerganov.com/whisper/ggml-tiny-es.bin || true
  fi
fi
cat > /usr/local/bin/hear.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
DEVICE_IN="${1:-}"
DUR="${2:-3}"
RATE="${3:-16000}"
MODEL="${4:-/opt/whisper.cpp/models/ggml-tiny-es.bin}"
TMP="/tmp/hear_$$.wav"

# 1) Si no se pasa dispositivo, intentar leer config JSON
if [[ -z "${DEVICE_IN}" ]]; then
  CFG_DIR="${BASCULA_CFG_DIR:-$HOME/.bascula}"
  CFG_PATH="${CFG_DIR}/config.json"
  if [[ -f "${CFG_PATH}" ]]; then
    DEV_FROM_CFG="$(python3 - "$CFG_PATH" <<'PY'
import json, sys
try:
    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        d = json.load(f)
    print(d.get('mic_device') or '')
except Exception:
    print('')
PY
)"
    if [[ -n "${DEV_FROM_CFG}" ]]; then DEVICE_IN="${DEV_FROM_CFG}"; fi
  fi
fi

# 2) Autodetección: primer dispositivo USB o primer card
if [[ -z "${DEVICE_IN}" ]]; then
  DEV_DET="$(arecord -l 2>/dev/null | awk -F'[ :]' '/^card [0-9]+:/{c=$3; l=tolower($0); if (index(l,"usb")>0 && c!=""){printf("plughw:%s,0\n",c); exit} } END{ if(c!=""){printf("plughw:%s,0\n",c)} }')"
  if [[ -n "${DEV_DET}" ]]; then DEVICE_IN="${DEV_DET}"; fi
fi

# 3) Fallback
DEVICE_IN="${DEVICE_IN:-plughw:1,0}"

arecord -D "${DEVICE_IN}" -f S16_LE -c 1 -r "${RATE}" "${TMP}" -d "${DUR}" >/dev/null 2>&1 || true
/opt/whisper.cpp/main -m "${MODEL}" -f "${TMP}" -l es -otxt -of /tmp/hear_result >/dev/null 2>&1 || true
rm -f "${TMP}" || true
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
if [[ "${NET_OK}" = "1" ]]; then
  source "${BASCULA_CURRENT_LINK}/.venv/bin/activate"
  # Seleccionar una versión de PaddlePaddle disponible en Piwheels/PyPI (2.6.x suele estar)
  PADDLE_VER_DEFAULT="2.6.2"
  PADDLE_VER="${PADDLE_VERSION:-${PADDLE_VER_DEFAULT}}"
  # Intento 1: versión fijada (por defecto 2.6.2)
  if ! python -m pip install --no-cache-dir "paddlepaddle==${PADDLE_VER}"; then
    # Intento 2: probar 2.6.1
    if ! python -m pip install --no-cache-dir "paddlepaddle==2.6.1"; then
      # Intento 3: probar 2.6.0
      if ! python -m pip install --no-cache-dir "paddlepaddle==2.6.0"; then
        warn "PaddlePaddle ${PADDLE_VER} no disponible; intentando sin fijar versión."
        python -m pip install --no-cache-dir paddlepaddle || warn "Instalación de PaddlePaddle falló; PaddleOCR puede no funcionar."
      fi
    fi
  fi
  # Instalar PaddleOCR y fallback ONNX; no romper si falla
  if ! python -m pip install --no-cache-dir paddleocr==2.7.0.3; then
    warn "PaddleOCR 2.7.0.3 no disponible; intentando última compatible."
    python -m pip install --no-cache-dir paddleocr || warn "Instalación de PaddleOCR falló; usa rapidocr-onnxruntime."
  fi
  python -m pip install --no-cache-dir rapidocr-onnxruntime || true
  deactivate
else
  warn "Sin red: omitiendo instalación de PaddlePaddle/PaddleOCR (se podrá instalar después)"
fi

# ---------- IA: Vision-lite (TFLite) ----------
if [[ "${NET_OK}" = "1" ]]; then
  "${VENV_PY}" -m pip install -q --no-cache-dir tflite-runtime==2.14.0 opencv-python-headless numpy || true
else
  warn "Sin red: omitiendo instalación de tflite-runtime/opencv en venv"
fi
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
  log "Dispatcher instalado (desde repo)."
else
  # Dispatcher mínimo integrado: levanta AP si no hay conectividad, lo baja si hay Internet.
  cat > /etc/NetworkManager/dispatcher.d/90-bascula-ap-fallback <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
AP_NAME="BasculaAP"
LOGTAG="bascula-ap-fallback"
log(){ printf "[nm-ap] %s\n" "$*"; logger -t "$LOGTAG" -- "$*" 2>/dev/null || true; }

# Descubrir interfaz Wi-Fi gestionada por NM (si existe)
get_wifi_iface(){
  local dev
  dev="$(nmcli -t -f DEVICE,TYPE,STATE device status 2>/dev/null | awk -F: '$2=="wifi"{print $1; exit}')"
  if [[ -z "$dev" ]] && command -v iw >/dev/null 2>&1; then
    dev="$(iw dev 2>/dev/null | awk '/Interface/{print $2; exit}')"
  fi
  printf '%s' "$dev"
}

ensure_wifi_on(){ nmcli radio wifi on >/dev/null 2>&1 || true; rfkill unblock wifi 2>/dev/null || true; }
has_inet(){ nmcli -t -f CONNECTIVITY general status 2>/dev/null | grep -qx "full"; }
# Wi-Fi infra activa (no AP)
wifi_connected(){
  local con mode
  con="$(nmcli -t -f TYPE,STATE,CONNECTION device status 2>/dev/null | awk -F: '$1=="wifi" && $2=="connected"{print $3; exit}')"
  if [[ -n "$con" ]]; then
    mode="$(nmcli -t -f 802-11-wireless.mode connection show "$con" 2>/dev/null | awk -F: 'NR==1{print $1}')"
    [[ "$mode" != "ap" ]]
    return $?
  fi
  return 1
}

up_ap(){
  local dev
  dev="$(get_wifi_iface)"
  if [[ -n "$dev" ]]; then
    nmcli connection up "$AP_NAME" ifname "$dev" >/dev/null 2>&1 && log "AP up (if=$dev)" || true
  else
    nmcli connection up "$AP_NAME" >/dev/null 2>&1 && log "AP up (autodev)" || true
  fi
}
down_ap(){ nmcli -t -f NAME,DEVICE connection show --active 2>/dev/null | grep -q "^${AP_NAME}:" && nmcli connection down "${AP_NAME}" >/dev/null 2>&1 && log "AP down" || true; }

case "${2:-}" in
  up|down|connectivity-change|hostname|dhcp4-change|dhcp6-change|vpn-up|vpn-down|pre-up|pre-down|carrier|vpn-pre-up|vpn-pre-down)
    : ;;
  *) : ;;
esac

ensure_wifi_on
if has_inet; then
  down_ap
else
  if wifi_connected; then
    down_ap
  else
    up_ap
  fi
fi
exit 0
EOF
  chmod 0755 /etc/NetworkManager/dispatcher.d/90-bascula-ap-fallback
  log "Dispatcher instalado (integrado por defecto)."
fi

# Crear/actualizar conexión AP de NM
set +e
nmcli connection show "${AP_NAME}" >/dev/null 2>&1
EXISTS=$?
set -e

if [[ ${EXISTS} -ne 0 ]]; then
  log "Creando conexión AP ${AP_NAME} (SSID=${AP_SSID}) en ${AP_IFACE}"
  nmcli connection add type wifi ifname "${AP_IFACE}" con-name "${AP_NAME}" autoconnect no ssid "${AP_SSID}" || true
else
  log "Actualizando conexión AP existente ${AP_NAME}"
  nmcli connection modify "${AP_NAME}" 802-11-wireless.ssid "${AP_SSID}" || true
fi
# Parametrización robusta del AP (forzar WPA2-PSK/AES y NAT IPv4 compartido)
nmcli connection modify "${AP_NAME}" \
  802-11-wireless.mode ap \
  802-11-wireless.band bg \
  802-11-wireless.channel 6 \
  ipv4.method shared \
  ipv6.method ignore || true

# Seguridad: forzar WPA2 (RSN) + CCMP y PSK explícito
nmcli connection modify "${AP_NAME}" \
  802-11-wireless-security.key-mgmt wpa-psk \
  802-11-wireless-security.proto rsn \
  802-11-wireless-security.group ccmp \
  802-11-wireless-security.pairwise ccmp \
  802-11-wireless-security.auth-alg open \
  802-11-wireless-security.psk "${AP_PASS}" \
  802-11-wireless-security.psk-flags 0 || true

nmcli connection modify "${AP_NAME}" connection.autoconnect no || true

# Asegurar RF no bloqueado y Wi-Fi levantado
rfkill unblock wifi 2>/dev/null || true
nmcli radio wifi on >/dev/null 2>&1 || true

# ---------- Habilitar servicios mini-web y UI ----------
# Instala bascula-web.service si no existe
if [[ ! -f /etc/systemd/system/bascula-web.service ]]; then
  if [[ -f "${BASCULA_CURRENT_LINK}/systemd/bascula-web.service" ]]; then
    cp "${BASCULA_CURRENT_LINK}/systemd/bascula-web.service" /etc/systemd/system/bascula-web.service
    # Drop-in override: usar usuario objetivo, venv y abrir a la red (0.0.0.0)
    mkdir -p /etc/systemd/system/bascula-web.service.d
    cat > /etc/systemd/system/bascula-web.service.d/override.conf <<EOF
[Service]
User=${TARGET_USER}
Group=${TARGET_GROUP}
WorkingDirectory=${BASCULA_CURRENT_LINK}
Environment=BASCULA_WEB_HOST=0.0.0.0
ExecStart=
ExecStart=${BASCULA_CURRENT_LINK}/.venv/bin/python -m bascula.services.wifi_config
# Menos estricto: permitir acceso en LAN/AP
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
IPAddressAllow=
IPAddressDeny=
# Desactivar endurecimientos que rompen el namespace al usar %h/.config
ProtectSystem=off
ProtectHome=off
PrivateTmp=false
RestrictNamespaces=false
ReadWritePaths=
EOF
    systemctl daemon-reload
    systemctl enable --now bascula-web.service || true
  fi
else
  systemctl enable --now bascula-web.service || true
fi

# Habilita servicios adicionales si existen
for svc in bascula-miniweb.service bascula-config.service; do
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

# X735 / PWM / Kernel
KV="$(uname -r 2>/dev/null || echo 0)"
if printf '%s\n%s\n' "6.6.22" "${KV}" | sort -V | head -n1 | grep -q '^6.6.22$'; then
  log "Kernel: ${KV} (>= 6.6.22)"
else
  warn "Kernel: ${KV} (< 6.6.22). Si el ventilador no gira, actualiza kernel."
fi
if [[ -d /sys/class/pwm/pwmchip2 ]]; then
  log "PWM: pwmchip2 presente"
else
  warn "PWM: pwmchip2 no encontrado (revisa overlay y kernel)"
fi
CONF_PATH="/boot/firmware/config.txt"; [[ -f /boot/config.txt ]] && CONF_PATH="/boot/config.txt"
if grep -q '^dtoverlay=pwm-2chan' "${CONF_PATH}" 2>/dev/null; then
  log "Overlay PWM: presente en ${CONF_PATH}"
else
  warn "Overlay PWM: no encontrado en ${CONF_PATH}"
fi
for svc in x735-fan.service x735-pwr.service; do
  if systemctl is-active --quiet "$svc"; then
    log "$svc: activo"
  else
    warn "$svc: inactivo"
  fi
done

# Piper TTS: binario y modelo
PVOICE_CHECK="${PIPER_VOICE:-es_ES-mls-medium}"
PIP_BIN="$(command -v piper 2>/dev/null || true)"
PIP_ONNX="/opt/piper/models/${PVOICE_CHECK}.onnx"
PIP_JSON="/opt/piper/models/${PVOICE_CHECK}.onnx.json"
if [[ -z "${PIP_BIN}" && -x "${BASCULA_CURRENT_LINK}/.venv/bin/piper" ]]; then PIP_BIN="${BASCULA_CURRENT_LINK}/.venv/bin/piper"; fi
if [[ -n "${PIP_BIN}" ]]; then
  if [[ -f "${PIP_ONNX}" && -f "${PIP_JSON}" ]]; then
    log "piper: OK (voz ${PVOICE_CHECK})"
  else
    warn "piper: binario OK, modelo/config no encontrado para '${PVOICE_CHECK}'"
  fi
else
  warn "piper: binario NO encontrado (se usará espeak-ng)"
fi

# Mini-web HTTP en AP (si BasculaAP activo)
if nmcli -t -f NAME,DEVICE connection show --active 2>/dev/null | grep -q "^${AP_NAME}:"; then
  HTTP_AP="$(curl -s -o /dev/null -w "%{http_code}" http://10.42.0.1:8080/ || echo 000)"
  if [[ "${HTTP_AP}" != "000" ]]; then
    log "mini-web en AP: responde (http://10.42.0.1:8080/, código ${HTTP_AP})"
  else
    warn "mini-web en AP: sin respuesta en http://10.42.0.1:8080/"
  fi
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

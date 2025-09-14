#!/usr/bin/env bash
set -euo pipefail

# scripts/install-all.sh — Bascula-Cam (Raspberry Pi 5, Bookworm Lite 64-bit)
# - Installs reproducible environment with isolated venv, services, and OTA structure
# - Configures HDMI (1024x600), KMS, I2S, PWM, UART, and NetworkManager AP fallback
# - Installs Piper TTS, Whisper.cpp ASR, Tesseract/PaddleOCR, TFLite, and services
# - Idempotent, with hard checks for service health and proper permissions
# - Supports offline installation with fallback directory

# --- Logging functions ---
log()  { printf "\033[1;34m[inst]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[warn]\033[0m %s\n" "$*"; }
err()  { printf "\033[1;31m[ERR ]\033[0m %s\n" "$*"; }

# --- Ensure root privileges ---
require_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    err "Run with sudo: sudo ./install-all.sh"
    exit 1
  fi
}
require_root

# --- Configuration variables ---
AP_SSID="${AP_SSID:-Bascula_AP}"
AP_PASS_RAW="${AP_PASS:-bascula1234}"
AP_IFACE="${AP_IFACE:-wlan0}"
AP_NAME="${AP_NAME:-BasculaAP}"

# Validate WPA2-PSK password (8-63 ASCII)
_len=${#AP_PASS_RAW}
if [[ ${_len} -lt 8 || ${_len} -gt 63 ]]; then
  warn "AP_PASS invalid (length ${_len}). Using default secure password."
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

BOOTDIR="/boot/firmware"
[[ ! -d "${BOOTDIR}" ]] && BOOTDIR="/boot"
CONF="${BOOTDIR}/config.txt"

OFFLINE_DIR="${BASCULA_OFFLINE_DIR:-/boot/bascula-offline}"

# --- Check existing installation ---
if [[ -L "${BASCULA_CURRENT_LINK}" && -d "${BASCULA_CURRENT_LINK}" ]]; then
  warn "Installation already exists at ${BASCULA_CURRENT_LINK}. Continuing idempotently."
fi


log "Target user      : $TARGET_USER ($TARGET_GROUP)"
log "Target home      : $TARGET_HOME"
log "OTA current link : $BASCULA_CURRENT_LINK"
log "AP (NM)          : SSID=${AP_SSID} PASS=${AP_PASS} IFACE=${AP_IFACE} profile=${AP_NAME}"
[[ -d "${OFFLINE_DIR}" ]] && log "Offline package  : ${OFFLINE_DIR}"

# --- Update and install base packages ---
apt-get update -y
if [[ "${RUN_FULL_UPGRADE:-0}" = "1" ]]; then
  apt-get full-upgrade -y || true
fi
if [[ "${RUN_RPI_UPDATE:-0}" = "1" ]] && command -v rpi-update >/dev/null 2>&1; then
  SKIP_WARNING=1 rpi-update || true
fi

apt-get install -y git curl ca-certificates build-essential cmake pkg-config \
  python3 python3-venv python3-pip python3-tk python3-numpy python3-serial \
  python3-pil.imagetk \
  x11-xserver-utils xserver-xorg xinit openbox \
  unclutter fonts-dejavu \
  libjpeg-dev zlib1g-dev libpng-dev \
  alsa-utils sox ffmpeg \
  libzbar0 gpiod python3-rpi.gpio \
  network-manager sqlite3 tesseract-ocr tesseract-ocr-spa espeak-ng
# --- Audio defaults (ALSA / HifiBerry) ---
# Selecciona la tarjeta HifiBerry (o primera no-HDMI) y fija /etc/asound.conf
CARD="$(aplay -l 2>/dev/null | awk -F'[ :]' '
  /snd_rpi_hifiberry_dac/ {print $3; found=1; exit}
  /USB Audio|PCM2902/      {print $3; found=1; exit}
  /^card [0-9]+:/          {if(!found && $3!="vc4hdmi0" && $3!="vc4hdmi1"){print $3; found=1}}
  END{if(!found) print 0}
')"

install -d -m 0755 /etc
cat > /etc/asound.conf <<EOF
# Bascula-Cam ALSA defaults (auto)
pcm.!default {
  type plug
  slave.pcm "dmix:CARD=${CARD},DEV=0"
}
ctl.!default {
  type hw
  card ${CARD}
}
EOF

# Sube volumen y desmutea (si existe el control)
amixer -c "${CARD}" sset Master 96% unmute >/dev/null 2>&1 || true
amixer -c "${CARD}" sset Digital 96% unmute >/dev/null 2>&1 || true
amixer -c "${CARD}" sset PCM 96% unmute    >/dev/null 2>&1 || true
alsactl store >/dev/null 2>&1 || true

echo "[inst] ALSA default set to card ${CARD} (see /etc/asound.conf)"
# --- end Audio defaults ---

# --- Check network connectivity ---
NET_OK=0
if curl -fsI -m 4 https://www.piwheels.org/simple >/dev/null 2>&1; then
  NET_OK=1
  log "PiWheels connectivity: OK"
else
  warn "PiWheels connectivity: NO (some pip/model downloads will be skipped)"
fi
[[ -d "${OFFLINE_DIR}" ]] && log "Offline package detected: ${OFFLINE_DIR}"

# --- Camera setup (Pi 5 / Bookworm) ---
for p in libcamera0 libcamera-ipa libcamera0.5 rpicam-apps python3-picamera2; do
  apt-mark unhold "$p" 2>/dev/null || true
done
CAM_LIB_PKGS=""
if apt-cache policy libcamera0.5 2>/dev/null | grep -q 'Candidate:'; then
  CAM_LIB_PKGS="libcamera-ipa libcamera0.5"
elif apt-cache policy libcamera0 2>/dev/null | grep -q 'Candidate:'; then
  CAM_LIB_PKGS="libcamera-ipa libcamera0"
fi
if [[ -n "${CAM_LIB_PKGS}" ]]; then
  apt-get install -y --no-install-recommends ${CAM_LIB_PKGS} || warn "libcamera installation failed (continuing)"
fi
if apt-cache policy rpicam-apps 2>/dev/null | grep -q 'Candidate:'; then
  apt-get install -y rpicam-apps || apt-get install -y libcamera-apps || true
else
  apt-get install -y libcamera-apps || true
fi
apt-get install -y --reinstall python3-picamera2 || true
python3 - <<'PY' 2>/dev/null || true
try:
    from picamera2 import Picamera2
    print("Picamera2 OK")
except Exception as e:
    print(f"Picamera2 NO OK: {e}")
PY

# --- UART setup ---
if [[ "${PHASE:-all}" != "2" ]]; then
  if [[ -f "${CONF}" ]] && ! grep -q "^enable_uart=1" "${CONF}"; then
    echo "enable_uart=1" >> "${CONF}"
  fi
  sed -i 's/console=serial0,115200 //g; s/console=ttyAMA0,115200 //g' "${BOOTDIR}/cmdline.txt" || true
  systemctl disable --now serial-getty@ttyAMA0.service serial-getty@ttyS0.service 2>/dev/null || true
  MODEL="$(tr -d '\0' </proc/device-tree/model 2>/dev/null || echo)"
  if ! echo "$MODEL" | grep -q "Raspberry Pi 5"; then
    if [[ -f "${CONF}" ]] && ! grep -q "^dtoverlay=disable-bt" "${CONF}"; then
      echo "dtoverlay=disable-bt" >> "${CONF}"
    fi
    systemctl disable --now hciuart 2>/dev/null || true
  fi

  # Añade el usuario al grupo 'dialout' (acceso a /dev/tty*)
if ! id -nG "$TARGET_USER" | tr ' ' '\n' | grep -qx "dialout"; then
  usermod -aG dialout "$TARGET_USER" || true
  log "Added $TARGET_USER to 'dialout' group (may require logout)"
fi

# Añade el usuario al grupo 'video' (acceso a /dev/video* y /dev/dri/*)
if ! id -nG "$TARGET_USER" | tr ' ' '\n' | grep -qx "video"; then
  usermod -aG video "$TARGET_USER" || true
  log "Added $TARGET_USER to 'video' group"
fi

  # Añade 'render' (acceso /dev/dri/renderD*)
  if ! id -nG "$TARGET_USER" | tr ' ' '\n' | grep -qx "render"; then
    usermod -aG render "$TARGET_USER" || true
    log "Added $TARGET_USER to 'render' group"
  fi
fi

# --- HDMI/KMS + I2S + PWM ---
if [[ "${PHASE:-all}" != "2" && -f "${CONF}" ]]; then
  # limpia el bloque previo (ok)
  sed -i '/# --- Bascula-Cam (Pi 5): Video + Audio I2S + PWM ---/,/# --- Bascula-Cam (end) ---/d' "${CONF}"

  # añade el bloque (faltaba esta línea)
  cat >> "${CONF}" <<'EOF'
# --- Bascula-Cam (Pi 5): Video + Audio I2S + PWM ---
hdmi_force_hotplug=1
hdmi_group=2
hdmi_mode=87
hdmi_cvt=1024 600 60 3 0 0 0
dtoverlay=vc4-kms-v3d
dtparam=audio=off
dtoverlay=i2s-mmap
dtoverlay=hifiberry-dac
dtoverlay=pwm-2chan,pin=12,func=4,pin2=13,func2=4
# --- Bascula-Cam (end) ---
EOF

  log "HDMI/KMS/I2S/PWM configured in ${CONF}"
fi


# --- EEPROM PSU_MAX_CURRENT ---
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

# --- Xwrapper ---
install -d -m 0755 /etc/X11
cat > "${XWRAPPER}" <<'EOF'
allowed_users=anybody
needs_root_rights=yes
EOF

# --- Polkit rules ---
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
cat > /etc/polkit-1/rules.d/51-bascula-systemd.rules <<EOF
polkit.addRule(function(action, subject) {
  var id = action.id;
  var unit = action.lookup("unit") || "";
  function allowed(u) {
    return u == "bascula-web.service" || u == "bascula-app.service" || u == "ocr-service.service";
  }
  if ((subject.user == "${TARGET_USER}" || subject.isInGroup("${TARGET_GROUP}")) &&
      (id == "org.freedesktop.systemd1.manage-units" ||
       id == "org.freedesktop.systemd1.restart-unit" ||
       id == "org.freedesktop.systemd1.start-unit" ||
       id == "org.freedesktop.systemd1.stop-unit") &&
      allowed(unit)) {
    return polkit.Result.YES;
  }
});
EOF
systemctl restart polkit NetworkManager || true

# --- WiFi detection ---
if ! nmcli -t -f DEVICE,TYPE device status 2>/dev/null | awk -F: -v d="${AP_IFACE}" '($1==d && $2=="wifi"){f=1} END{exit f?0:1}'; then
  _WDEV="$(nmcli -t -f DEVICE,TYPE,STATE device status 2>/dev/null | awk -F: '$2=="wifi"{print $1; exit}')"
  if [[ -z "${_WDEV}" ]] && command -v iw >/dev/null 2>&1; then
    _WDEV="$(iw dev 2>/dev/null | awk '/Interface/{print $2; exit}')"
  fi
  if [[ -n "${_WDEV}" ]]; then
    AP_IFACE="${_WDEV}"
    log "WiFi interface detected: ${AP_IFACE}"
  else
    warn "No WiFi interface found; using ${AP_IFACE}"
  fi
  unset _WDEV
fi

# --- WiFi connectivity (pre-OTA) ---
WIFI_SSID="${WIFI_SSID:-}"
WIFI_PASS="${WIFI_PASS:-}"
WIFI_HIDDEN="${WIFI_HIDDEN:-0}"
WIFI_COUNTRY="${WIFI_COUNTRY:-}"
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
            if ssid:
                break
        i += 1
    def dq(x):
        if x is None: return ''
        x = x.strip()
        if len(x) >= 2 and x[0] == '"' and x[-1] == '"':
            return x[1:-1]
        return x
    print(dq(ssid))
    print(dq(psk))
    print('1' if str(scan_ssid).strip() in ('1','true','True') else '0')
    print(country)
except Exception:
    pass
PY
)
      WIFI_SSID="${_WF[0]:-}"
      WIFI_PASS="${_WF[1]:-}"
      WIFI_HIDDEN="${_WF[2]:-0}"
      if [[ -z "${WIFI_COUNTRY}" ]]; then WIFI_COUNTRY="${_WF[3]:-}"; fi
      unset _WF
      if [[ -n "${WIFI_SSID}" ]]; then
        log "WiFi credentials imported from ${WCONF} (SSID=${WIFI_SSID})"
        break
      fi
    fi
  done
fi
if [[ -n "${WIFI_COUNTRY}" ]] && command -v iw >/dev/null 2>&1; then
  iw reg set "${WIFI_COUNTRY}" 2>/dev/null || true
fi

have_inet() { curl -fsI -m 4 https://deb.debian.org >/dev/null 2>&1 || curl -fsI -m 4 https://www.piwheels.org/simple >/dev/null 2>&1; }
wifi_active() { nmcli -t -f TYPE,STATE connection show --active 2>/dev/null | grep -q '^wifi:activated$'; }
ap_active() { nmcli -t -f NAME,DEVICE connection show --active 2>/dev/null | grep -q "^${AP_NAME}:"; }

rfkill unblock wifi 2>/dev/null || true
nmcli radio wifi on >/dev/null 2>&1 || true
nmcli device set "${AP_IFACE}" managed yes >/dev/null 2>&1 || true
if ap_active; then nmcli connection down "${AP_NAME}" >/dev/null 2>&1 || true; fi

if [[ -n "${WIFI_SSID}" ]]; then
  nmcli device wifi rescan ifname "${AP_IFACE}" >/dev/null 2>&1 || true
  nmcli -t -f NAME connection show | grep -qx "BasculaWiFi" || nmcli connection add type wifi ifname "${AP_IFACE}" con-name "BasculaWiFi" ssid "${WIFI_SSID}" || true
  nmcli connection modify "BasculaWiFi" 802-11-wireless.ssid "${WIFI_SSID}" || true
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
  log "Pre-OTA connectivity: OK"
else
  warn "No Internet for OTA. Attempting with local fallback if available."
fi

# --- OTA: Clone repository ---
if [[ "${PHASE:-all}" == "1" || "${PHASE:-all}" == "phase1" || "${PHASE:-all}" == "system" ]]; then
  log "Phase 1 completed. Reboot and run: sudo PHASE=2 ./install-all.sh"
  exit 0
fi

install -d -m 0755 "${BASCULA_RELEASES_DIR}"
if [[ ! -e "${BASCULA_CURRENT_LINK}" ]]; then
  DEST="${BASCULA_RELEASES_DIR}/v1"
  if [[ "${NET_OK}" = "1" ]] && git ls-remote https://github.com/DanielGTdiabetes/bascula-cam.git >/dev/null 2>&1; then
    log "Cloning repository to ${DEST}..."
    git clone https://github.com/DanielGTdiabetes/bascula-cam.git "${DEST}"
  else
    SRC_DIR="${BASCULA_SOURCE_DIR:-}"
    if [[ -z "${SRC_DIR}" ]]; then
      _SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
      _CANDIDATE="$(cd "${_SCRIPT_DIR}/.." && pwd)"
      if ROOT_GIT="$(git -C "${_CANDIDATE}" rev-parse --show-toplevel 2>/dev/null || true)" && [[ -n "${ROOT_GIT}" ]]; then
        SRC_DIR="${ROOT_GIT}"
      else
        SRC_DIR="${_CANDIDATE}"
      fi
      unset _SCRIPT_DIR _CANDIDATE ROOT_GIT
    fi
    if [[ -d "${SRC_DIR}" && -f "${SRC_DIR}/scripts/install-all.sh" && -d "${SRC_DIR}/bascula" ]]; then
      log "No GitHub access. Using local repository: ${SRC_DIR}"
      install -d -m 0755 "${DEST}"
      (cd "${SRC_DIR}" && tar --exclude .git --exclude .venv --exclude __pycache__ --exclude '*.pyc' -cf - .) | tar -xf - -C "${DEST}"
    else
      err "No GitHub access and no valid local repository found."
      err "Options:"
      err "  - Connect to Internet and retry"
      err "  - Set BASCULA_SOURCE_DIR to the repository path and retry"
      err "  - Manually create/adjust ${BASCULA_CURRENT_LINK} -> ${DEST}"
      exit 1
    fi
  fi
  ln -s "${DEST}" "${BASCULA_CURRENT_LINK}"
fi
chown -R "${TARGET_USER}:${TARGET_GROUP}" "${BASCULA_ROOT}"
install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_GROUP}" /var/log/bascula

# --- Virtual environment ---
cd "${BASCULA_CURRENT_LINK}"
if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi
VENV_DIR="${BASCULA_CURRENT_LINK}/.venv"
VENV_PY="${VENV_DIR}/bin/python"
VENV_PIP="${VENV_DIR}/bin/pip"
export PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore PIP_PREFER_BINARY=1
export PIP_INDEX_URL="https://www.piwheels.org/simple"
export PIP_EXTRA_INDEX_URL="https://pypi.org/simple"

if [[ "${NET_OK}" = "1" ]]; then
  "${VENV_PIP}" install -q --upgrade pip wheel setuptools
  NUMPY_VERSION=$(python3 -c "import numpy; print(numpy.__version__)" 2>/dev/null || echo "1.26.4")
  "${VENV_PIP}" install -q "numpy==${NUMPY_VERSION}" pyserial pillow Flask>=2.2 fastapi "uvicorn[standard]" pytesseract requests pyzbar "pytz>=2024.1" piper-tts
  if [[ -f "requirements.txt" ]]; then
    grep -viE '^[[:space:]]*(numpy|picamera2|pymupdf|fitz)\b' requirements.txt > /tmp/reqs.$$.txt || true
    if [[ -s /tmp/reqs.$$.txt ]]; then
      "${VENV_PIP}" install -q -r /tmp/reqs.$$.txt || true
    fi
    rm -f /tmp/reqs.$$.txt
  fi
  if [[ -x "${VENV_DIR}/bin/piper" ]] && ! command -v piper >/dev/null 2>&1; then
    ln -sf "${VENV_DIR}/bin/piper" /usr/local/bin/piper || true
  fi
elif [[ -d "${OFFLINE_DIR}/wheels" ]]; then
  log "Installing venv dependencies from offline wheels (${OFFLINE_DIR}/wheels)"
  "${VENV_PIP}" install -q --no-index --find-links "${OFFLINE_DIR}/wheels" \
    numpy pyserial pillow Flask fastapi uvicorn pytesseract requests pyzbar pytz piper-tts || true
else
  warn "No network and no offline wheels: Skipping venv dependency installation"
fi
"${VENV_PIP}" install -q python-multipart || true
# --- Picamera2 bridge + simplejpeg rebuild (Bascula patch) ---
# 1) Asegura que el venv vea /usr/lib/python3/dist-packages (picamera2 de Debian)
VENV_SITE="$(${VENV_PY} - <<'PY'
import sysconfig
print(sysconfig.get_paths().get('purelib'))
PY
)"
if [ -n "${VENV_SITE}" ] && [ -d "${VENV_SITE}" ]; then
  echo "/usr/lib/python3/dist-packages" > "${VENV_SITE}/system_dist.pth"
fi

# 2) Evita incompatibilidad ABI de simplejpeg (con NumPy) recompilándolo en el venv
apt-get install -y --no-install-recommends python3-dev pkg-config libjpeg-dev zlib1g-dev || true
"${VENV_PIP}" uninstall -y simplejpeg >/dev/null 2>&1 || true
# usa la misma versión que tengas o la estable (1.8.2). Fuerza build desde fuentes
"${VENV_PIP}" install --no-binary=:all: --force-reinstall "simplejpeg==1.8.2" || \
"${VENV_PIP}" install --no-binary=:all: --force-reinstall simplejpeg || true

# 3) Smoke-test: importar Picamera2 dentro del venv sin PYTHONPATH
"${VENV_PY}" - <<'PY' || true
try:
    from picamera2 import Picamera2
    print("VENV Picamera2: OK")
except Exception as e:
    print("VENV Picamera2: FAIL ->", e)
PY
# --- end Bascula patch ---

# --- X735 fan/power services ---
install -d -m 0755 /opt
if [[ ! -d /opt/x735-script/.git ]]; then
  git clone https://github.com/geekworm-com/x735-script /opt/x735-script || true
fi
if [[ -d /opt/x735-script ]]; then
  cd /opt/x735-script || true
  chmod +x *.sh || true
  sed -i 's/pwmchip0/pwmchip2/g' x735-fan.sh 2>/dev/null || true
  ./install-fan-service.sh || true
  ./install-pwr-service.sh || true
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
  systemctl enable --now x735-fan.service x735-pwr.service 2>/dev/null || true
  cp -f ./xSoft.sh /usr/local/bin/ 2>/dev/null || true
  if ! grep -q 'alias x735off=' "${TARGET_HOME}/.bashrc" 2>/dev/null; then
    echo 'alias x735off="sudo /usr/local/bin/xSoft.sh 0 20"' >> "${TARGET_HOME}/.bashrc"
    chown "${TARGET_USER}:${TARGET_GROUP}" "${TARGET_HOME}/.bashrc" || true
  fi
fi

cat > /usr/local/sbin/x735-ensure.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
STAMP=/var/lib/x735-setup.done
LOG(){ printf "[x735] %s\n" "$*"; }

PWMCHIP=
for c in /sys/class/pwm/pwmchip2 /sys/class/pwm/pwmchip1 /sys/class/pwm/pwmchip0; do
  if [[ -d "$c" ]]; then PWMCHIP="${c##*/}"; break; fi
done
if [[ -z "${PWMCHIP}" ]]; then
  LOG "PWM not available; retry on next boot"
  exit 0
fi

if [[ ! -d /opt/x735-script/.git ]]; then
  git clone https://github.com/geekworm-com/x735-script /opt/x735-script || true
fi
cd /opt/x735-script || exit 0
chmod +x *.sh || true
sed -i "s/pwmchip[0-9]\+/${PWMCHIP}/g" x735-fan.sh 2>/dev/null || true
./install-fan-service.sh || true
./install-pwr-service.sh || true
systemctl enable --now x735-fan.service x735-pwr.service 2>/dev/null || true
touch "${STAMP}"
LOG "X735 setup completed (pwmchip=${PWMCHIP})"
exit 0
EOF
chmod 0755 /usr/local/sbin/x735-ensure.sh
install -d -m 0755 /var/lib
cat > /etc/systemd/system/x735-ensure.service <<'EOF'
[Unit]
Description=Ensure X735 fan/power services
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

# --- Piper TTS + say.sh ---
if apt-cache policy piper 2>/dev/null | grep -q 'Candidate:'; then
  apt-get install -y piper || true
elif [[ "${NET_OK}" = "1" ]]; then
  "${VENV_PIP}" install -q piper-tts || true
fi
if ! command -v piper >/dev/null 2>&1; then
  if [[ -d "${OFFLINE_DIR}" ]]; then
    F_BIN_OFF="$(find "${OFFLINE_DIR}" -maxdepth 3 -type f -name 'piper' 2>/dev/null | head -n1)"
    if [[ -n "${F_BIN_OFF}" ]]; then
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
    armv7l) PIPER_BIN_URL="https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_armv7l.tar.gz" ;;
    x86_64) PIPER_BIN_URL="https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_x86_64.tar.gz" ;;
  esac
  if [[ -n "${PIPER_BIN_URL}" && "${NET_OK}" = "1" ]]; then
    install -d -m 0755 /opt/piper/bin
    TMP_TGZ="/tmp/piper_bin_$$.tgz"
    if curl -fL --retry 2 -m 20 -o "${TMP_TGZ}" "${PIPER_BIN_URL}" 2>/dev/null && tar -tzf "${TMP_TGZ}" >/dev/null 2>&1; then
      tar -xzf "${TMP_TGZ}" -C /opt/piper/bin || true
      rm -f "${TMP_TGZ}" || true
      F_BIN="$(find /opt/piper/bin -maxdepth 2 -type f -name 'piper' | head -n1)"
      if [[ -n "${F_BIN}" ]]; then
        chmod +x "${F_BIN}" || true
        ln -sf "${F_BIN}" /usr/local/bin/piper || true
      fi
    else
      warn "Piper binary download failed for ARCH=${ARCH}. Using espeak-ng as fallback."
    fi
  fi
fi

cat > "${SAY_BIN}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
TEXT="${*:-}"
[ -z "$TEXT" ] && exit 0
BIN="$(command -v piper || echo "/opt/bascula/current/.venv/bin/piper")"
if [[ -z "${PIPER_VOICE:-}" && -f "/opt/piper/models/.default-voice" ]]; then
  PIPER_VOICE="$(cat /opt/piper/models/.default-voice 2>/dev/null || true)"
fi
VOICE="${PIPER_VOICE:-es_ES-mls_10246-medium}"
MODEL="/opt/piper/models/${VOICE}.onnx"
CONFIG="/opt/piper/models/${VOICE}.onnx.json"
if [[ ! -f "${CONFIG}" ]]; then
  base="${MODEL%.onnx}"
  if [[ -f "${base}.onnx.json" ]]; then CONFIG="${base}.onnx.json";
  elif [[ -f "${base}.json" ]]; then CONFIG="${base}.json";
  else
    CJSON="$(find /opt/piper/models -maxdepth 2 -type f \( -name '*.onnx.json' -o -name '*.json' \) 2>/dev/null | head -n1 || true)"
    [[ -n "${CJSON}" ]] && CONFIG="${CJSON}"
  fi
fi
if [[ -x "${BIN}" && -f "${MODEL}" && -f "${CONFIG}" ]]; then
  echo -n "${TEXT}" | "${BIN}" -m "${MODEL}" -c "${CONFIG}" --length-scale 0.97 --noise-scale 0.5 --noise-w 0.7 | aplay -q -r 22050 -f S16_LE -t raw -
else
  espeak-ng -v es -s 170 "${TEXT}" >/dev/null 2>&1 || true
fi
EOF
chmod 0755 "${SAY_BIN}"

# --- Mic test ---
cat > "${MIC_TEST}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
CARD_DEVICE="${1:-plughw:1,0}"
DUR="${2:-5}"
RATE="${3:-16000}"
OUT="/tmp/mic_test.wav"
echo "[mic-test] Recording ${DUR}s from ${CARD_DEVICE} at ${RATE} Hz..."
arecord -D "${CARD_DEVICE}" -f S16_LE -c 1 -r "${RATE}" "${OUT}" -d "${DUR}"
echo "[mic-test] Playing ${OUT}..."
aplay "${OUT}"
EOF
chmod 0755 "${MIC_TEST}"

# --- ASR (whisper.cpp) ---
install -d -m 0755 /opt/whisper.cpp/models
if [[ -d /opt/whisper.cpp ]]; then
  if git -C /opt/whisper.cpp rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git -C /opt/whisper.cpp pull --ff-only || true
  else
    warn "/opt/whisper.cpp exists but is not a git repo. Backing up and recloning."
    mv /opt/whisper.cpp "/opt/whisper.cpp.bak.$(date +%s)" || true
    git clone https://github.com/ggerganov/whisper.cpp /opt/whisper.cpp || true
  fi
else
  git clone https://github.com/ggerganov/whisper.cpp /opt/whisper.cpp || true
fi
make -C /opt/whisper.cpp -j"$(nproc)" || true
if [[ ! -f /opt/whisper.cpp/models/ggml-tiny-es.bin ]]; then
  if [[ -f "${OFFLINE_DIR}/whisper/ggml-tiny-es.bin" ]]; then
    cp -f "${OFFLINE_DIR}/whisper/ggml-tiny-es.bin" /opt/whisper.cpp/models/ggml-tiny-es.bin || true
  elif [[ "${NET_OK}" = "1" ]]; then
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
if [[ -z "${DEVICE_IN}" ]]; then
  DEV_DET="$(arecord -l 2>/dev/null | awk -F'[ :]' '/^card [0-9]+:/{c=$3; l=tolower($0); if (index(l,"usb")>0 && c!=""){printf("plughw:%s,0\n",c); exit} } END{ if(c!=""){printf("plughw:%s,0\n",c)} }')"
  if [[ -n "${DEV_DET}" ]]; then DEVICE_IN="${DEV_DET}"; fi
fi
DEVICE_IN="${DEVICE_IN:-plughw:1,0}"
arecord -D "${DEVICE_IN}" -f S16_LE -c 1 -r "${RATE}" "${TMP}" -d "${DUR}" >/dev/null 2>&1 || true
/opt/whisper.cpp/main -m "${MODEL}" -f "${TMP}" -l es -otxt -of /tmp/hear_result >/dev/null 2>&1 || true
rm -f "${TMP}" || true
if [[ -f /tmp/hear_result.txt ]]; then sed 's/^[[:space:]]*//;s/[[:space:]]*$//' /tmp/hear_result.txt; else echo ""; fi
EOF
chmod 0755 /usr/local/bin/hear.sh

# --- OCR service (Tesseract + FastAPI) ---
install -d -m 0755 /opt/ocr-service
cat > /opt/ocr-service/app.py <<'PY'
import io
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import JSONResponse, PlainTextResponse
from PIL import Image
import pytesseract
app = FastAPI(title="OCR Service", version="1.0")
@app.get("/health")
async def health():
    return {"status": "ok"}
@app.get("/")
async def root():
    return PlainTextResponse("ok")
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
cat > /etc/systemd/system/ocr-service.service <<EOF
[Unit]
Description=Bascula OCR Service (FastAPI)
After=network.target

[Service]
Type=simple
User=${TARGET_USER}
Group=${TARGET_GROUP}
WorkingDirectory=/opt/ocr-service
Environment=PYTHONPATH=/usr/lib/python3/dist-packages
ExecStart=${BASCULA_CURRENT_LINK}/.venv/bin/python -m uvicorn app:app --host 127.0.0.1 --port 8078
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
# --- OCR deps hard-check (ejecutado por el instalador, no dentro de la unit) ---
"${BASCULA_CURRENT_LINK}/.venv/bin/python" - <<'PY' || { echo "[ERR ] OCR deps missing (fastapi/uvicorn/PIL/pytesseract/pyzbar/multipart)"; exit 1; }
import importlib
for m in ("fastapi","uvicorn","PIL","pytesseract","pyzbar","multipart"):
    importlib.import_module(m)
print("OCR_DEPS_OK")
PY
echo "[inst] Voces Piper desde GitHub Release"
set -e

# Asegura herramientas
apt-get update
apt-get install -y piper jq sox curl

# Carpeta de voces del sistema
install -d -m 0755 /opt/piper/models

# Descarga voces desde el último Release del repositorio
GH_API="https://api.github.com/repos/DanielGTdiabetes/bascula-cam/releases/latest"
GH_JSON="$(curl -fsSL "$GH_API" 2>/dev/null || true)"
for f in \
  es_ES-mls_10246-medium.onnx es_ES-mls_10246-medium.onnx.json \
  es_ES-sharvard-medium.onnx  es_ES-sharvard-medium.onnx.json
do
  if [ ! -s "/opt/piper/models/$f" ]; then
    url="$(printf '%s' "$GH_JSON" | jq -r --arg N "$f" '.assets[] | select(.name==$N) | .browser_download_url' 2>/dev/null)"
    if [ -n "$url" ] && [ "$url" != "null" ]; then
      echo "  - $f"
      curl -fL --retry 4 --retry-delay 2 --continue-at - \
        -o "/opt/piper/models/$f" \
        "$url"
    else
      warn "No encontré $f en GitHub Release (saltando)"
    fi
  fi
done
echo "[ok  ] Voces Piper listas"
# Wrapper "say.sh" para usar Piper fácilmente (VERSIÓN CORREGIDA)
cat >/usr/local/bin/say.sh <<'EOS'
#!/usr/bin/env bash
# Uso:
#   say.sh "texto a decir"
#   say.sh -v es_ES-sharvard-medium "texto"
#   say.sh -d plughw:1,0 "texto"  # ejemplo salida ALSA

VOICE="es_ES-sharvard-medium"
DEVICE="" # p.ej. DEVICE="-D plughw:1,0"

# parseo simple de -v y -d
while [[ "$1" == -* ]]; do
  case "$1" in
    -v|--voice) VOICE="$2"; shift 2;;
    -d|--device) DEVICE="-D $2"; shift 2;;
    *) break;;
  esac
done

TEXT="${*:-Prueba de voz}"

# --- RUTA CORREGIDA ---
MODEL_DIR="/opt/piper/models"
# ----------------------

# Parámetros que mejoran inteligibilidad
OPTS=(--length-scale 1.1 --noise-scale 0.333 --noise-w 0.667)

TMPWAV="$(mktemp --suffix=.wav)"
# --- USAR RUTA CORRECTA ---
piper --model "${MODEL_DIR}/${VOICE}.onnx" \
      --config "${MODEL_DIR}/${VOICE}.onnx.json" \
      "${OPTS[@]}" <<<"$TEXT" > "$TMPWAV" || exit 1

if command -v pw-play >/dev/null 2>&1 && [[ -z "$DEVICE" ]]; then
  pw-play "$TMPWAV"
else
  aplay ${DEVICE} "$TMPWAV"
fi
rm -f "$TMPWAV"
EOS
chmod +x /usr/local/bin/say.sh

# Prueba silenciosa para dejar constancia en logs
(say.sh -v es_ES-sharvard-medium "Instalación de voces completada." >/dev/null 2>&1 || true)

"${BASCULA_CURRENT_LINK}/.venv/bin/python" - <<'PY' || true
try:
    from PIL import Image, ImageTk
    print("Pillow+ImageTk: OK")
except Exception as e:
    print("Pillow+ImageTk: FAIL ->", e)
PY

systemctl reset-failed ocr-service || true
systemctl daemon-reload
systemctl restart ocr-service
# --- end OCR deps hard-check ---
systemctl daemon-reload
systemctl enable --now ocr-service.service || true

# --- PaddleOCR ---
if [[ "${INSTALL_PADDLEOCR:-0}" = "1" && "${NET_OK}" = "1" ]]; then
  source "${BASCULA_CURRENT_LINK}/.venv/bin/activate"
  PADDLE_VER_DEFAULT="2.6.2"
  PADDLE_VER="${PADDLE_VERSION:-${PADDLE_VER_DEFAULT}}"
  if ! python -m pip install --no-cache-dir "paddlepaddle==${PADDLE_VER}"; then
    if ! python -m pip install --no-cache-dir "paddlepaddle==2.6.1"; then
      if ! python -m pip install --no-cache-dir "paddlepaddle==2.6.0"; then
        warn "PaddlePaddle ${PADDLE_VER} not available; trying latest."
        python -m pip install --no-cache-dir paddlepaddle || warn "PaddlePaddle installation failed."
      fi
    fi
  fi
  if ! python -m pip install --no-cache-dir paddleocr==2.7.0.3; then
    warn "PaddleOCR 2.7.0.3 not available; trying latest."
    python -m pip install --no-cache-dir paddleocr || warn "PaddleOCR installation failed."
  fi
  python -m pip install --no-cache-dir rapidocr-onnxruntime || true
  deactivate
elif [[ "${INSTALL_PADDLEOCR:-0}" = "1" ]]; then
  warn "No network: Skipping PaddlePaddle/PaddleOCR installation"
else
  log "Installing rapidocr-onnxruntime as PaddleOCR alternative"
  "${VENV_PIP}" install -q rapidocr-onnxruntime || true
fi

# --- Vision-lite (TFLite) ---
if [[ "${NET_OK}" = "1" ]]; then
  "${VENV_PIP}" install -q --no-deps tflite-runtime==2.14.0 opencv-python-headless || true
else
  warn "No network: Skipping tflite-runtime/opencv installation"
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

# --- WiFi AP Fallback (NetworkManager) ---
install -d -m 0755 /etc/NetworkManager/dispatcher.d
REPO_ROOT="${BASCULA_CURRENT_LINK}"
SRC_DISPATCH="${REPO_ROOT}/scripts/nm-dispatcher/90-bascula-ap-fallback"
if [[ -f "${SRC_DISPATCH}" ]]; then
  install -m 0755 "${SRC_DISPATCH}" /etc/NetworkManager/dispatcher.d/90-bascula-ap-fallback
  log "Dispatcher installed (from repo)."
else
  cat > /etc/NetworkManager/dispatcher.d/90-bascula-ap-fallback <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
AP_NAME="BasculaAP"
LOGTAG="bascula-ap-fallback"
log(){ printf "[nm-ap] %s\n" "$*"; logger -t "$LOGTAG" -- "$*" 2>/dev/null || true; }

get_wifi_iface(){
  local dev
  dev="$(nmcli -t -f DEVICE,TYPE,STATE device status 2>/dev/null | awk -F: '$2=="wifi"{print $1; exit}')"
  if [[ -z "$dev" ]] && command -v iw >/dev/null 2>&1; then
    dev="$(iw dev 2>/dev/null | awk '/Interface/{print $2; exit}')"
  fi
  printf '%s' "$dev"
}

ensure_wifi_on(){ nmcli radio wifi on >/dev/null 2>&1 || true; rfkill unblock wifi 2>/dev/null || true; }
has_inet(){ curl -fsI -m 4 https://deb.debian.org >/dev/null 2>&1; }
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
  log "Dispatcher installed (default)."
fi

set +e
nmcli connection show "${AP_NAME}" >/dev/null 2>&1
EXISTS=$?
set -e
if [[ ${EXISTS} -ne 0 ]]; then
  log "Creating AP connection ${AP_NAME} (SSID=${AP_SSID}) on ${AP_IFACE}"
  nmcli connection add type wifi ifname "${AP_IFACE}" con-name "${AP_NAME}" autoconnect no ssid "${AP_SSID}" || true
else
  log "Updating existing AP connection ${AP_NAME}"
  nmcli connection modify "${AP_NAME}" 802-11-wireless.ssid "${AP_SSID}" || true
fi
nmcli connection modify "${AP_NAME}" \
  802-11-wireless.mode ap \
  802-11-wireless.band bg \
  802-11-wireless.channel 6 \
  ipv4.method shared \
  ipv6.method ignore \
  802-11-wireless-security.key-mgmt wpa-psk \
  802-11-wireless-security.proto rsn \
  802-11-wireless-security.group ccmp \
  802-11-wireless-security.pairwise ccmp \
  802-11-wireless-security.auth-alg open \
  802-11-wireless-security.psk "${AP_PASS}" \
  802-11-wireless-security.psk-flags 0 \
  connection.autoconnect no || true
nmcli radio wifi on >/dev/null 2>&1 || true
rfkill unblock wifi 2>/dev/null || true

# --- Mini-web service ---
cat > /etc/systemd/system/bascula-web.service <<EOF
[Unit]
Description=Bascula Web Configuration Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${TARGET_USER}
Group=${TARGET_GROUP}
WorkingDirectory=${BASCULA_CURRENT_LINK}
Environment=HOME=${TARGET_HOME}
Environment=XDG_CONFIG_HOME=${TARGET_HOME}/.config
Environment=PYTHONPATH=/usr/lib/python3/dist-packages
Environment=BASCULA_WEB_HOST=0.0.0.0
Environment=BASCULA_WEB_PORT=8080
Environment=BASCULA_CFG_DIR=${TARGET_HOME}/.config/bascula
ExecStart=${BASCULA_CURRENT_LINK}/.venv/bin/python -m bascula.services.wifi_config
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_GROUP}" "${TARGET_HOME}/.config/bascula" || true
# Preflight: ensure port 8080 is free
if ss -ltn '( sport = :8080 )' | grep -q ':8080'; then
  warn "Port 8080 is already in use. bascula-web will not start. Free the port or set BASCULA_WEB_PORT."
fi
systemctl enable --now bascula-web.service || true
su -s /bin/bash -c 'mkdir -p ~/.config/bascula' "${TARGET_USER}" || true

# --- UI service ---
cat > "${XSESSION}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
export DISPLAY=:0
export PYTHONPATH=/usr/lib/python3/dist-packages
xset s off || true
xset -dpms || true
xset s noblank || true
unclutter -idle 0 -root &
cd /opt/bascula/current || true
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
Environment=PYTHONPATH=/usr/lib/python3/dist-packages
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
systemctl enable --now bascula-app.service || true

# --- tmpfiles for logs ---
cat > "${TMPFILES}" <<EOF
d /run/bascula 0755 ${TARGET_USER} ${TARGET_GROUP} -
f /run/bascula.alive 0666 ${TARGET_USER} ${TARGET_GROUP} -
EOF
systemd-tmpfiles --create "${TMPFILES}" || true

# --- Permissions ---
chown -R "${TARGET_USER}:${TARGET_GROUP}" /opt/bascula /opt/ocr-service

# --- Hard checks ---
log "Running post-installation checks..."
VENV_PY="${BASCULA_CURRENT_LINK}/.venv/bin/python"

# pyzbar + libzbar
if ldconfig -p 2>/dev/null | grep -q "zbar"; then
  log "libzbar: OK"
else
  warn "libzbar: NOT FOUND (install libzbar0)"
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
  warn "pyzbar+Pillow: FAILED -> ${PYZBAR_OUT}"
fi

# Picamera2
PIC_OUT="$(PYTHONPATH=/usr/lib/python3/dist-packages python3 - <<'PY' 2>/dev/null || true
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
  warn "Picamera2: FAILED -> ${PIC_OUT}"
fi

# OCR service
for i in {1..8}; do
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8078/ || echo 000)
  if [[ "${HTTP_CODE}" == "200" ]]; then
    log "OCR service: Responding (HTTP ${HTTP_CODE})"
    break
  fi
  warn "OCR service: Not responding (attempt ${i}/8)"
  sleep 2
  systemctl restart ocr-service.service || true
done
if [[ "${HTTP_CODE}" != "200" ]]; then
  err "OCR service failed to respond after 8 attempts"
  exit 1
fi

# Mini-web service
for i in {1..8}; do
  HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/ || echo 000)
  if [[ "${HTTP_CODE}" == "200" || "${HTTP_CODE}" == "404" ]]; then
    log "Mini-web service: Responding (HTTP ${HTTP_CODE})"
    break
  fi
  warn "Mini-web service: Not responding (attempt ${i}/8)"
  sleep 2
  install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_GROUP}" "${TARGET_HOME}/.config/bascula" || true
systemctl restart bascula-web.service || true
done
if [[ "${HTTP_CODE}" != "200" && "${HTTP_CODE}" != "404" ]]; then
  err "Mini-web service failed to respond after 8 attempts"
  exit 1
fi

# X735 / PWM / Kernel
KV="$(uname -r 2>/dev/null || echo 0)"
if printf '%s\n%s\n' "6.6.22" "${KV}" | sort -V | head -n1 | grep -q '^6.6.22$'; then
  log "Kernel: ${KV} (>= 6.6.22)"
else
  warn "Kernel: ${KV} (< 6.6.22). Fan may not work; update kernel."
fi
if [[ -d /sys/class/pwm/pwmchip2 ]]; then
  log "PWM: pwmchip2 present"
else
  warn "PWM: pwmchip2 not found (check overlay/kernel)"
fi
if grep -q '^dtoverlay=pwm-2chan' "${CONF}" 2>/dev/null; then
  log "Overlay PWM: Present in ${CONF}"
else
  warn "Overlay PWM: Not found in ${CONF}"
fi
for svc in x735-fan.service x735-pwr.service; do
  if systemctl is-active --quiet "$svc"; then
    log "$svc: Active"
  else
    warn "$svc: Inactive"
  fi
done

# Piper TTS
PIP_BIN="$(command -v piper 2>/dev/null || true)"
if [[ -z "${PIP_BIN}" && -x "${BASCULA_CURRENT_LINK}/.venv/bin/piper" ]]; then PIP_BIN="${BASCULA_CURRENT_LINK}/.venv/bin/piper"; fi
if [[ -n "${PIP_BIN}" ]]; then
  CHECK_VOICE="${PIPER_VOICE:-es_ES-mls_10246-medium}"
  if [[ -f /opt/piper/models/.default-voice ]]; then
    CHECK_VOICE="$(cat /opt/piper/models/.default-voice 2>/dev/null || echo "${CHECK_VOICE}")"
  fi
  PIP_ONNX="/opt/piper/models/${CHECK_VOICE}.onnx"
  PIP_JSON="/opt/piper/models/${CHECK_VOICE}.onnx.json"
  if [[ -f "${PIP_ONNX}" && -f "${PIP_JSON}" ]]; then
    log "Piper: OK (voice ${CHECK_VOICE})"
    if echo 'Instalación correcta' | "${PIP_BIN}" -m "${PIP_ONNX}" -c "${PIP_JSON}" >/dev/null 2>&1; then
      log "Piper TTS: OK (synthesis 'Instalación correcta')"
    else
      warn "Piper TTS: Synthesis failed (binary/model present)"
    fi
  else
    warn "Piper: Binary OK, model/config not found"
  fi
else
  warn "Piper: Binary not found (using espeak-ng)"
fi

# --- Final message ---
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo "----------------------------------------------------"
echo "Installation completed."
echo "Logs: /var/log/bascula"
echo "Active release: ${BASCULA_CURRENT_LINK}"
echo "Mini-web: http://${IP:-<IP>}:8080/"
echo "OCR: http://127.0.0.1:8078/ocr"
echo "AP: SSID=${AP_SSID} PASS=${AP_PASS} IFACE=${AP_IFACE} profile=${AP_NAME}"
echo "Reboot to apply overlays: sudo reboot"
if command -v /usr/local/bin/say.sh >/dev/null 2>&1; then
  /usr/local/bin/say.sh "Instalacion correcta" >/dev/null 2>&1 || true
elif command -v espeak-ng >/dev/null 2>&1; then
  espeak-ng -v es -s 170 "Instalacion correcta" >/dev/null 2>&1 || true
fi

#!/usr/bin/env bash
set -euo pipefail

# Resolve absolute path to this script before any directory changes occur.
if command -v readlink >/dev/null 2>&1; then
  _INSTALL_SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
else
  pushd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null || exit 1
  _INSTALL_SCRIPT_PATH="$(pwd -P)/$(basename "${BASH_SOURCE[0]}")"
  popd >/dev/null || exit 1
fi
SCRIPT_DIR_ABS="$(dirname "${_INSTALL_SCRIPT_PATH}")"
unset _INSTALL_SCRIPT_PATH

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

pip_retry() {
  local attempt
  local cmd_desc="$*"
  for attempt in 1 2 3; do
    if "$@"; then
      return 0
    fi
    if (( attempt < 3 )); then
      echo "[pip] Intento ${attempt} fallido para ${cmd_desc}; reintentando…" >&2
      sleep 3
    fi
  done
  echo "[pip] ERROR instalando tras 3 intentos: ${cmd_desc}" >&2
  return 1
}

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
TARGET_GROUP="${TARGET_GROUP:-${TARGET_USER}}"
if ! getent group "${TARGET_GROUP}" >/dev/null 2>&1; then
  TARGET_GROUP="$(id -gn "$TARGET_USER" 2>/dev/null || echo "${TARGET_USER}")"
fi
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
  x11-xserver-utils xserver-xorg xinit openbox \
  unclutter fonts-dejavu \
  libjpeg-dev zlib1g-dev libpng-dev \
  alsa-utils sox ffmpeg \
  libzbar0 gpiod python3-rpi.gpio \
  network-manager sqlite3 tesseract-ocr tesseract-ocr-spa espeak-ng

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
  if ! id -nG "$TARGET_USER" | tr ' ' '\n' | grep -qx "dialout"; then
    usermod -aG dialout "$TARGET_USER" || true
    log "Added $TARGET_USER to 'dialout' group (may require logout)"
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
  function allowed() {
    return subject.user == "${TARGET_USER}" ||
           subject.isInGroup("${TARGET_GROUP}") ||
           subject.user == "bascula" ||
           subject.isInGroup("bascula");
  }
  if (!allowed()) return polkit.Result.NOT_HANDLED;

  const id = action.id;
  if (id == "org.freedesktop.NetworkManager.settings.modify.system" ||
      id == "org.freedesktop.NetworkManager.network-control" ||
      id == "org.freedesktop.NetworkManager.enable-disable-wifi") {
    return polkit.Result.YES;
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
      _SCRIPT_DIR="${SCRIPT_DIR_ABS}"
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

install -d -m 0755 /opt/piper/models
PIPER_VOICE="${PIPER_VOICE:-es_ES-mls_10246-medium}"
VOICES=(
  "${PIPER_VOICE}"
  "es_ES-mls_10246-low"
  "es_ES-carlfm-medium"
  "es_ES-mls-medium"
)

for V in "${VOICES[@]}"; do
  CURRENT_VOICE_ONNX="/opt/piper/models/${V}.onnx"
  CURRENT_VOICE_JSON="/opt/piper/models/${V}.onnx.json"

  # Ya existe
  if [[ -f "${CURRENT_VOICE_ONNX}" && -f "${CURRENT_VOICE_JSON}" ]]; then
    log "Piper voice '${V}' already exists. Skipping download."
    PIPER_VOICE="${V}"
    echo "${PIPER_VOICE}" > /opt/piper/models/.default-voice 2>/dev/null || true
    break
  fi

  # 1) Preferir repo local: /opt/bascula/current/voices/<VOICE>/<VOICE>.onnx(.json)
  LOCAL_BASE="/opt/bascula/current/voices/${V}"
  if [[ -f "${LOCAL_BASE}/${V}.onnx" && -f "${LOCAL_BASE}/${V}.onnx.json" ]]; then
    install -m 0644 "${LOCAL_BASE}/${V}.onnx"       "${CURRENT_VOICE_ONNX}"
    install -m 0644 "${LOCAL_BASE}/${V}.onnx.json"  "${CURRENT_VOICE_JSON}"
    PIPER_VOICE="${V}"
    echo "${PIPER_VOICE}" > /opt/piper/models/.default-voice 2>/dev/null || true
    log "Piper voice '${V}' copied from local repo."
    break
  fi

  # 2) Hugging Face (layout real ONNX+JSON)
  locale="${V%%-*}"                 # es_ES
  rest="${V#*-}"                    # mls_10246-medium
  quality="${rest##*-}"             # medium
  corpus="${rest%-${quality}}"      # mls_10246
  base="https://huggingface.co/rhasspy/piper-voices/resolve/main"
  U_ONNX="${base}/es/${locale}/${corpus}/${quality}/${V}.onnx"
  U_JSON="${base}/es/${locale}/${corpus}/${quality}/${V}.onnx.json"

  if [[ "${NET_OK}" = "1" ]]; then
    if curl -fIL -m 20 -L "${U_ONNX}" >/dev/null 2>&1; then
      curl -fL --retry 3 -m 180 -o "${CURRENT_VOICE_ONNX}" "${U_ONNX}" || true
    else
      warn "Piper ONNX not reachable: ${U_ONNX}"
    fi
    if curl -fIL -m 20 -L "${U_JSON}" >/dev/null 2>&1; then
      curl -fL --retry 3 -m 60 -o "${CURRENT_VOICE_JSON}" "${U_JSON}" || true
    else
      warn "Piper JSON not reachable: ${U_JSON}"
    fi
  fi

  if [[ -f "${CURRENT_VOICE_ONNX}" && -f "${CURRENT_VOICE_JSON}" ]]; then
    PIPER_VOICE="${V}"
    echo "${PIPER_VOICE}" > /opt/piper/models/.default-voice 2>/dev/null || true
    log "Piper voice '${PIPER_VOICE}' installed successfully."
    break
  fi
done

if [[ ! -f "/opt/piper/models/${PIPER_VOICE}.onnx" ]]; then
  warn "Failed to obtain Piper voices (tried: ${VOICES[*]}). Using espeak-ng as fallback."
fi


cat > "${SAY_BIN}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
TEXT="${*:-}"
[ -z "$TEXT" ] && exit 0
BIN="$(command -v piper || echo "${BASCULA_CURRENT_LINK}/.venv/bin/piper")"
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
systemctl daemon-reload
systemctl reset-failed ocr-service.service 2>/dev/null || true
systemctl enable ocr-service.service
systemctl restart ocr-service.service
# --- end OCR deps hard-check ---

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
  pip_retry "${VENV_PIP}" install -q --no-deps tflite-runtime==2.14.0 opencv-python-headless || true
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
SRC_DISPATCH="${REPO_ROOT}/scripts/nm-dispatcher/90-bascula-ap"
if [[ -f "${SRC_DISPATCH}" ]]; then
  install -m 0755 "${SRC_DISPATCH}" /etc/NetworkManager/dispatcher.d/90-bascula-ap
  log "Dispatcher installed (from repo)."
else
  cat > /etc/NetworkManager/dispatcher.d/90-bascula-ap <<'EOF'
#!/usr/bin/env bash
# Instalación fallback - controla el AP BasculaAP según conectividad.
set -euo pipefail
AP_NAME="${AP_NAME:-BasculaAP}"
AP_IFACE="${AP_IFACE:-wlan0}"
STATE_FILE="/run/bascula-ap.state"
LOCK_FILE="/run/bascula-ap.lock"
LOGTAG="bascula-ap"

log(){
  local msg="$*"
  printf '[nm-ap] %s\n' "$msg"
  logger -t "$LOGTAG" -- "$msg" 2>/dev/null || true
}

has_default_route(){
  ip -4 route show default 2>/dev/null | grep -q . && return 0
  ip -6 route show default 2>/dev/null | grep -q .
}

nm_state(){
  nmcli -t -f STATE general status 2>/dev/null | head -n1 || printf 'unknown'
}

eth_connected(){
  nmcli -t -f DEVICE,TYPE,STATE device status 2>/dev/null |
    awk -F: '$1=="eth0" && $3=="connected"{exit 0} END{exit 1}'
}

wifi_client_connected(){
  local line conn
  line="$(nmcli -t -f DEVICE,TYPE,STATE,CONNECTION device status 2>/dev/null |
    awk -F: '$2=="wifi" && $3=="connected"{print $1":"$4; exit}')"
  [[ -z "$line" ]] && return 1
  conn="${line#*:}"
  [[ -n "$conn" && "$conn" != "$AP_NAME" ]]
}

ap_is_active(){
  nmcli -t -f NAME connection show --active 2>/dev/null | grep -Fxq "$AP_NAME"
}

read_state(){
  if [[ -s "$STATE_FILE" ]]; then
    tr -d '\n' < "$STATE_FILE"
  else
    printf 'unknown'
  fi
}

write_state(){
  local new_state="$1"
  umask 022
  printf '%s\n' "$new_state" > "${STATE_FILE}.tmp"
  mv "${STATE_FILE}.tmp" "$STATE_FILE"
}

ensure_wifi_on(){
  nmcli radio wifi on >/dev/null 2>&1 || true
  rfkill unblock wifi 2>/dev/null || true
}

bring_up(){
  ensure_wifi_on
  if ap_is_active; then
    write_state up
    return 0
  fi
  sleep 1
  if nmcli -w 10 connection up "$AP_NAME" ifname "$AP_IFACE" >/dev/null 2>&1 || \
     nmcli -w 10 connection up "$AP_NAME" >/dev/null 2>&1; then
    write_state up
    log "AP up (if=${AP_IFACE})"
    return 0
  fi
  log "Failed to bring up ${AP_NAME}"
  return 1
}

bring_down(){
  if ! ap_is_active && [[ "$(read_state)" == "down" ]]; then
    return 0
  fi
  sleep 1
  if nmcli connection down "$AP_NAME" >/dev/null 2>&1 || ! ap_is_active; then
    write_state down
    log "AP down"
    return 0
  fi
  return 1
}

main(){
  if command -v flock >/dev/null 2>&1; then
    exec 9>"$LOCK_FILE"
    flock -n 9 || exit 0
  fi

  local current_state desired_state nm_status have_route
  current_state="$(read_state)"
  desired_state="$current_state"
  if [[ "$desired_state" != "up" && "$desired_state" != "down" ]]; then
    desired_state="down"
  fi

  nm_status="$(nm_state)"
  have_route=0
  if has_default_route; then
    have_route=1
  fi

  if [[ "$nm_status" != "connected" && "$have_route" -eq 0 ]]; then
    desired_state="up"
  elif [[ "$have_route" -eq 1 ]] && (eth_connected || wifi_client_connected); then
    desired_state="down"
  fi

  if [[ "$desired_state" == "up" ]]; then
    if [[ "$current_state" != "up" ]] || ! ap_is_active; then
      bring_up || true
    fi
  else
    if [[ "$current_state" != "down" ]] || ap_is_active; then
      bring_down || true
    fi
  fi

  log "state=${current_state}->${desired_state} nm=${nm_status} route=${have_route}"
}

main "$@"
EOF
  chmod 0755 /etc/NetworkManager/dispatcher.d/90-bascula-ap
  log "Dispatcher installed (fallback)."
fi

if ! nmcli -t -f NAME connection show | grep -qx "${AP_NAME}"; then
  log "Creating AP connection ${AP_NAME} (SSID=${AP_SSID}) on ${AP_IFACE}"
fi
nmcli -t -f NAME connection show | grep -qx "${AP_NAME}" || \
  nmcli connection add type wifi ifname "${AP_IFACE}" con-name "${AP_NAME}" ssid "${AP_SSID}" || true

nmcli connection modify "${AP_NAME}" \
  connection.id "${AP_NAME}" \
  connection.interface-name "${AP_IFACE}" \
  802-11-wireless.mode ap \
  802-11-wireless.band bg \
  802-11-wireless.channel 6 \
  802-11-wireless.ssid "${AP_SSID}" \
  802-11-wireless-security.key-mgmt wpa-psk \
  802-11-wireless-security.proto rsn \
  802-11-wireless-security.group ccmp \
  802-11-wireless-security.pairwise ccmp \
  802-11-wireless-security.auth-alg open \
  802-11-wireless-security.psk "${AP_PASS}" \
  802-11-wireless-security.psk-flags 0 \
  ipv4.method shared \
  ipv6.method ignore \
  connection.autoconnect no \
  connection.autoconnect-priority 0 \
  connection.autoconnect-retries 0 || true
nmcli radio wifi on >/dev/null 2>&1 || true
rfkill unblock wifi 2>/dev/null || true

nmcli connection down "${AP_NAME}" >/dev/null 2>&1 || true
/etc/NetworkManager/dispatcher.d/90-bascula-ap || true

# --- Mini-web and UI services (systemd) ---
install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_GROUP}" "${TARGET_HOME}/.config/bascula"
install -d -m 0755 /etc/bascula
install -m 0644 /dev/null /etc/bascula/WEB_READY
install -m 0644 /dev/null /etc/bascula/APP_READY

# Determine the repository source directory for script copies.
REPO_SRC_DIR="${BASCULA_SOURCE_DIR:-${SRC_DIR:-}}"
if [[ -z "${REPO_SRC_DIR}" ]]; then
  REPO_SRC_DIR="$(cd "${SCRIPT_DIR_ABS}/.." && pwd -P)"
fi

for f in xsession.sh net-fallback.sh recovery_xsession.sh recovery_retry.sh recovery_update.sh recovery_wifi.sh; do
  src="${REPO_SRC_DIR}/scripts/${f}"
  dest="${BASCULA_CURRENT_LINK}/scripts/${f}"
  if [[ -f "${src}" ]]; then
    if [[ -e "${dest}" && "${src}" -ef "${dest}" ]]; then
      continue
    fi
    install -D -m 0755 "${src}" "${dest}"
  else
    warn "Missing script source: ${src} (skipping)"
  fi
done

install -D -m 0644 "${BASCULA_CURRENT_LINK}/systemd/bascula-web.service" /etc/systemd/system/bascula-web.service
install -D -m 0644 "${BASCULA_CURRENT_LINK}/systemd/bascula-web.service.d/10-writable-home.conf" /etc/systemd/system/bascula-web.service.d/10-writable-home.conf
install -D -m 0644 "${BASCULA_CURRENT_LINK}/systemd/bascula-web.service.d/20-env-and-exec.conf" /etc/systemd/system/bascula-web.service.d/20-env-and-exec.conf
install -D -m 0644 "${BASCULA_CURRENT_LINK}/systemd/bascula-net-fallback.service" /etc/systemd/system/bascula-net-fallback.service
install -D -m 0644 "${BASCULA_CURRENT_LINK}/systemd/bascula-app.service" /etc/systemd/system/bascula-app.service
install -D -m 0644 "${BASCULA_CURRENT_LINK}/systemd/bascula-recovery.service" /etc/systemd/system/bascula-recovery.service
install -D -m 0644 "${BASCULA_CURRENT_LINK}/systemd/bascula-recovery.target" /etc/systemd/system/bascula-recovery.target
install -D -m 0644 "${BASCULA_CURRENT_LINK}/systemd/bascula-alarmd.service" /etc/systemd/system/bascula-alarmd.service

systemctl disable getty@tty1.service || true
systemctl daemon-reload
systemctl enable --now bascula-web.service bascula-net-fallback.service bascula-app.service bascula-alarmd.service || true

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

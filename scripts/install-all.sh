#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOCAL_VENV_DIR="${PROJECT_ROOT}/.venv"
LOCAL_PYTHON=""
LOCAL_PIP=""
OFFLINE_DIR="${BASCULA_OFFLINE_DIR:-/boot/bascula-offline}"

# scripts/install-all.sh — Bascula-Cam (Raspberry Pi 5, Bookworm Lite 64-bit)
# - Installs reproducible environment with isolated venv, services, and OTA structure
# - Configures HDMI (1024x600), KMS, I2S, PWM, UART, and NetworkManager AP fallback
# - Installs Piper TTS, Whisper.cpp ASR, Tesseract/PaddleOCR, TFLite, and services
# - Idempotent, with hard checks for service health and proper permissions
# - Supports offline installation with fallback directory

# --- Logging functions ---
log()  { printf "\033[1;34m[inst]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[inst][warn]\033[0m %s\n" "$*"; }
err()  { printf "\033[1;31m[inst][err ]\033[0m %s\n" "$*"; }

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

parse_kv() {
  local file="$1"
  local key="$2"
  [[ -f "$file" ]] || return 0
  awk -v k="$key" '
    /^[[:space:]]*(#|$)/ {next}
    /^[[:space:]]*(export[[:space:]]+)?[A-Za-z_][A-Za-z0-9_]*[[:space:]]*=/ {
      line=$0
      sub(/\r$/, "", line)
      sub(/^[[:space:]]*/, "", line)
      sub(/^export[[:space:]]+/, "", line)
      split(line, parts, "=")
      name=parts[1]
      sub(/[[:space:]]*$/, "", name)
      if (name==k) {
        value=line
        sub(/^[^=]*=/, "", value)
        gsub(/^[[:space:]]*/, "", value)
        gsub(/[[:space:]]*$/, "", value)
        gsub(/^[[:space:]]*"/, "", value)
        gsub(/"[[:space:]]*$/, "", value)
        gsub(/^[[:space:]]*\047/, "", value)
        gsub(/\047[[:space:]]*$/, "", value)
        print value
        exit
      }
    }
  ' "$file" 2>/dev/null
}

sanitize_literal() {
  case "$1" in
    *'$('*|*'`'*|*'${'*|*';'*|*'&'*|*'|'*|*'<'*|*'>'* ) return 1 ;;
    * ) return 0 ;;
  esac
}

resolve_miniweb_port() {
  local port
  if [[ -n "${BASCULA_MINIWEB_PORT_OVERRIDE:-}" ]]; then
    printf '%s' "${BASCULA_MINIWEB_PORT_OVERRIDE}"
    return
  fi
  if ! command -v systemctl >/dev/null 2>&1; then
    printf '%s' '8080'
    return
  fi
  port="$(systemctl show -p Environment bascula-miniweb.service 2>/dev/null \
    | sed -n 's/^Environment=//p' \
    | tr ' ' '\n' \
    | sed -n 's/^BASCULA_MINIWEB_PORT=//p' \
    | tail -n1)"
  if [[ -z "${port}" ]]; then
    port="$(systemctl cat bascula-miniweb.service 2>/dev/null \
      | awk '
          /ExecStart=/ {
            for (i = 1; i <= NF; i++) {
              if ($i ~ /^--port$/ && (i + 1) <= NF) {
                print $(i + 1);
                exit;
              }
              if ($i ~ /^--port=/) {
                sub(/^--port=/, "", $i);
                print $i;
                exit;
              }
            }
          }
        ')"
  fi
  if [[ -z "${port}" ]]; then
    port=8080
  fi
  printf '%s' "${port}"
}

ensure_python_runtime() {
  SYSTEM_PYTHON="${SYSTEM_PYTHON:-$(command -v python3 || true)}"
  if [[ -z "${SYSTEM_PYTHON}" ]]; then
    err "python3 no encontrado en el sistema"
    exit 1
  fi
  PYTHON_VERSION="$(${SYSTEM_PYTHON} -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  if ! ${SYSTEM_PYTHON} - <<'PY'
import sys
sys.exit(0 if sys.version_info[:2] >= (3, 11) else 1)
PY
  then
    err "Python >= 3.11 requerido, encontrado ${PYTHON_VERSION}"
    exit 1
  fi
}

ensure_local_venv() {
  if [[ -z "${LOCAL_VENV_DIR:-}" ]]; then
    err "LOCAL_VENV_DIR no definido"
    exit 1
  fi
  if [[ ! -d "${LOCAL_VENV_DIR}" ]]; then
    log "Creando entorno virtual local en ${LOCAL_VENV_DIR}"
    if ! ${SYSTEM_PYTHON} -m venv "${LOCAL_VENV_DIR}" >/dev/null 2>&1; then
      if [[ "${SKIP_INSTALL_ALL_PACKAGES:-0}" != "1" ]]; then
        apt-get update
        apt-get install -y python3-venv python3-pip python3-dev
      else
        err "python3-venv requerido para crear ${LOCAL_VENV_DIR}."
        err "Vuelve a ejecutar sin SKIP_INSTALL_ALL_PACKAGES=1 o instala python3-venv manualmente."
        exit 1
      fi
      ${SYSTEM_PYTHON} -m venv "${LOCAL_VENV_DIR}"
    fi
  fi
  if [[ ! -f "${LOCAL_VENV_DIR}/bin/activate" ]]; then
    err "Entorno virtual corrupto en ${LOCAL_VENV_DIR}"
    exit 1
  fi
  # shellcheck disable=SC1091
  source "${LOCAL_VENV_DIR}/bin/activate"
  LOCAL_PYTHON="${LOCAL_VENV_DIR}/bin/python"
  LOCAL_PIP="${LOCAL_VENV_DIR}/bin/pip"
  local site_dir
  site_dir="$(${LOCAL_PYTHON} - <<'PY'
import sysconfig
print(sysconfig.get_paths().get('purelib', ''))
PY
)"
  if [[ -n "${site_dir}" && -d "${site_dir}" ]]; then
    echo "/usr/lib/python3/dist-packages" > "${site_dir}/system_dist.pth"
  fi
}

install_local_requirements() {
  if [[ -z "${LOCAL_PYTHON:-}" ]]; then
    err "LOCAL_PYTHON no está inicializado"
    exit 1
  fi
  export PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore PIP_PREFER_BINARY=1
  local req_file="${PROJECT_ROOT}/requirements.txt"
  if [[ "${NET_OK:-0}" = "1" ]]; then
    export PIP_INDEX_URL="https://www.piwheels.org/simple"
    export PIP_EXTRA_INDEX_URL="https://pypi.org/simple"
    pip_retry "${LOCAL_PYTHON}" -m pip install --upgrade pip wheel setuptools
    if [[ -f "${req_file}" ]]; then
      pip_retry "${LOCAL_PYTHON}" -m pip install -r "${req_file}"
    fi
  elif [[ -d "${OFFLINE_DIR}/wheels" ]]; then
    warn "Sin conectividad a Internet; instalando dependencias locales desde ${OFFLINE_DIR}/wheels"
    pip_retry "${LOCAL_PYTHON}" -m pip install --no-index --find-links "${OFFLINE_DIR}/wheels" --upgrade pip wheel setuptools || true
    if [[ -f "${req_file}" ]]; then
      pip_retry "${LOCAL_PYTHON}" -m pip install --no-index --find-links "${OFFLINE_DIR}/wheels" -r "${req_file}"
    fi
  else
    err "No hay conectividad ni ruedas offline para instalar requirements.txt"
    err "Conecta a Internet o coloca las ruedas en ${OFFLINE_DIR}/wheels"
    exit 1
  fi
}

check_network_connectivity() {
  local url="https://www.piwheels.org/simple"
  if command -v curl >/dev/null 2>&1; then
    if curl -fsI -m 4 "${url}" >/dev/null 2>&1; then
      return 0
    fi
  fi
  if command -v wget >/dev/null 2>&1; then
    if wget --spider -q -T 4 "${url}" >/dev/null 2>&1; then
      return 0
    fi
  fi
  if [[ -n "${SYSTEM_PYTHON:-}" ]]; then
    if "${SYSTEM_PYTHON}" - <<'PY' 2>/dev/null; then
import ssl
import urllib.request
try:
    urllib.request.urlopen("https://www.piwheels.org/simple", timeout=4)
except Exception:
    raise SystemExit(1)
raise SystemExit(0)
PY
      return 0
    fi
  fi
  return 1
}


# detect_playback_card determines the preferred ALSA playback device and fills ALSA_* globals.
detect_playback_card() {
  ALSA_CARD_ID=""
  ALSA_CARD_DEV=""
  ALSA_CARD_INDEX=""
  ALSA_CARD_LABEL=""
  if ! command -v aplay >/dev/null 2>&1; then
    return 1
  fi

  local line
  local card_index=""
  local card_name=""
  local card_label=""
  local dev=""
  local first_index=""
  local first_dev=""
  local first_label=""

  while IFS= read -r line; do
    if [[ ${line} =~ ^card[[:space:]]+([0-9]+):[[:space:]]+([^[:space:]]+)[[:space:]]+\[(.*)\] ]]; then
      card_index="${BASH_REMATCH[1]}"
      card_name="${BASH_REMATCH[2]}"
      card_label="${BASH_REMATCH[3]}"
    elif [[ ${line} =~ ^[[:space:]]*device[[:space:]]+([0-9]+): ]]; then
      dev="${BASH_REMATCH[1]}"
      if [[ -z "${first_index}" ]]; then
        first_index="${card_index}"
        first_dev="${dev}"
        first_label="${card_label}"
      fi
      if [[ "${card_label}" == "snd_rpi_hifiberry_dac" || "${card_name}" == "sndrpihifiberry" ]]; then
        ALSA_CARD_ID="sndrpihifiberry"
        ALSA_CARD_DEV="0"
        ALSA_CARD_INDEX="${card_index}"
        ALSA_CARD_LABEL="${card_label}"
        return 0
      fi
    fi
  done < <(aplay -l 2>/dev/null)

  if [[ -n "${first_index}" && -n "${first_dev}" ]]; then
    ALSA_CARD_ID="${first_index}"
    ALSA_CARD_DEV="${first_dev}"
    ALSA_CARD_INDEX="${first_index}"
    ALSA_CARD_LABEL="${first_label}"
    return 0
  fi

  return 1
}

# write_global_asound updates /etc/asound.conf with the detected playback defaults.
write_global_asound() {
  local card_id="$1"
  local dev="$2"
  local dest="/etc/asound.conf"
  local tmp
  tmp="$(mktemp)"
  cat <<EOF >"${tmp}"
pcm.!default {
    type plug
    slave {
        pcm "hw:${card_id},${dev}"
    }
}
ctl.!default {
    type hw
    card ${card_id}
}
EOF

  if [[ -f "${dest}" ]]; then
    if cmp -s "${tmp}" "${dest}"; then
      log "[audio] unchanged ${dest}"
      rm -f "${tmp}"
      return 0
    fi
    local ts
    ts="$(date +%Y%m%d%H%M%S)"
    cp -p "${dest}" "${dest}.bak.${ts}" 2>/dev/null || true
    log "[audio] backup ${dest} -> ${dest}.bak.${ts}"
  fi

  if ! install -o root -g root -m 0644 "${tmp}" "${dest}"; then
    rm -f "${tmp}"
    log "[audio] WARN failed to write ${dest}"
    return 1
  fi
  rm -f "${tmp}"
  log "[audio] wrote ${dest}"
  return 0
}

# write_user_asound mirrors the ALSA defaults into each service user's home directory.
write_user_asound() {
  local user="$1"
  local card_id="$2"
  local dev="$3"
  local passwd_entry
  passwd_entry="$(getent passwd "${user}" || true)"
  if [[ -z "${passwd_entry}" ]]; then
    log "[audio] WARN user=${user} (passwd entry missing)"
    return 1
  fi
  local home
  home="$(printf '%s\n' "${passwd_entry}" | cut -d: -f6)"
  if [[ -z "${home}" || ! -d "${home}" ]]; then
    log "[audio] WARN user=${user} (home not found)"
    return 1
  fi
  local group
  group="$(id -gn "${user}" 2>/dev/null || printf '%s' "${user}")"
  local dest="${home}/.asoundrc"
  local tmp
  tmp="$(mktemp)"
  cat <<EOF >"${tmp}"
pcm.!default {
    type plug
    slave {
        pcm "hw:${card_id},${dev}"
    }
}
ctl.!default {
    type hw
    card ${card_id}
}
EOF

  if [[ -f "${dest}" ]] && cmp -s "${tmp}" "${dest}"; then
    log "[audio] unchanged ~${user}/.asoundrc"
    rm -f "${tmp}"
    return 0
  fi

  if ! install -o "${user}" -g "${group}" -m 0644 "${tmp}" "${dest}"; then
    rm -f "${tmp}"
    log "[audio] WARN user=${user} (write failed)"
    return 1
  fi
  rm -f "${tmp}"
  log "[audio] wrote ~${user}/.asoundrc"
  return 0
}

# test_user_audio executes speaker-test for each user and logs the outcome without aborting.
test_user_audio() {
  local user="$1"
  local card_id="$2"
  local dev="$3"
  if ! command -v speaker-test >/dev/null 2>&1; then
    log "[audio] WARN user=${user} (speaker-test not available)"
    return 1
  fi
  local attempt
  for attempt in 1 2; do
    if timeout 5s sudo -u "${user}" -H bash -lc 'speaker-test -c2 -twav -l1' >/dev/null 2>&1; then
      log "[audio] OK user=${user} (default)"
      return 0
    fi
    if (( attempt == 1 )); then
      sleep 1
    fi
  done
  log "[audio] WARN user=${user} (default failed). Prueba: speaker-test -D hw:${card_id},${dev} -c2 -twav -l1"
  return 1
}

# collect_service_users builds the list of unique service users running bascula units.
collect_service_users() {
  local search_dir
  local unit_file
  local user
  local -A seen=()
  SERVICE_USERS=()

  if [[ -n "${TARGET_USER:-}" ]]; then
    SERVICE_USERS+=("${TARGET_USER}")
    seen["${TARGET_USER}"]=1
  fi

  for search_dir in /etc/systemd/system /lib/systemd/system; do
    [[ -d "${search_dir}" ]] || continue
    while IFS= read -r -d '' unit_file; do
      user="$(awk -F= '
        function trim(x){gsub(/^[[:space:]]+|[[:space:]]+$/, "", x); return x}
        {
          left = trim($1)
          if (tolower(left) == "user") {
            print trim($2)
            exit
          }
        }
      ' "${unit_file}" 2>/dev/null)"
      if [[ -z "${user}" ]]; then
        user="root"
      fi
      if [[ -z "${seen[$user]:-}" ]]; then
        SERVICE_USERS+=("${user}")
        seen["${user}"]=1
      fi
    done < <(find "${search_dir}" -maxdepth 1 -type f -name 'bascula-*.service' -print0 2>/dev/null)
  done
}

voice_selftest() {
  local phrase="Prueba de voz"
  if command -v say.sh >/dev/null 2>&1; then
    if timeout 15s say.sh "${phrase}" >/dev/null 2>&1; then
      log "Prueba de voz OK mediante say.sh"
      return 0
    fi
    warn "say.sh disponible pero la prueba de voz falló"
    return 1
  fi
  if command -v piper >/dev/null 2>&1; then
    local voice="${PIPER_VOICE:-es_ES-mls_10246-medium}"
    if [[ -f /opt/piper/models/.default-voice ]]; then
      voice="$(cat /opt/piper/models/.default-voice 2>/dev/null || echo "${voice}")"
    fi
    local model="/opt/piper/models/${voice}.onnx"
    local config="/opt/piper/models/${voice}.onnx.json"
    if [[ -f "${model}" && -f "${config}" ]]; then
      if echo "${phrase}" | timeout 20s piper --model "${model}" --config "${config}" >/dev/null 2>&1; then
        log "Prueba de voz OK mediante piper (${voice})"
        return 0
      fi
      warn "piper disponible pero falló la síntesis de voz (${voice})"
      return 1
    fi
    warn "piper encontrado pero no se halló el modelo ${voice}; omitiendo prueba"
    return 1
  fi
  warn "No se encontró binario de voz para la prueba (--with-piper)"
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

# --- Parse arguments ---
WITH_PIPER_FLAG=0
REMAINING_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-piper)
      WITH_PIPER_FLAG=1
      shift
      ;;
    *)
      REMAINING_ARGS+=("$1")
      shift
      ;;
  esac
done
set -- "${REMAINING_ARGS[@]}"

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
if [[ -z "${TARGET_HOME}" ]]; then
  err "No se pudo determinar el home de ${TARGET_USER}"
  exit 1
fi

ensure_python_runtime
ensure_local_venv
export PATH="${LOCAL_VENV_DIR}/bin:${PATH}"
NET_OK=0
if check_network_connectivity; then
  NET_OK=1
  log "PiWheels connectivity: OK"
else
  warn "PiWheels connectivity: NO (some pip/model downloads will be skipped)"
fi
[[ -d "${OFFLINE_DIR}" ]] && log "Offline package detected: ${OFFLINE_DIR}"
log "Sincronizando dependencias en ${LOCAL_VENV_DIR} para el instalador"
install_local_requirements
PYTHON_BIN="${LOCAL_VENV_DIR}/bin/python"

CFG_DIR="${BASCULA_SETTINGS_DIR:-${TARGET_HOME}/.bascula}"
CFG_PATH="${CFG_DIR}/config.json"
if [[ ! -s "${CFG_PATH}" ]]; then
  log "Generando ~/.bascula/config.json con valores seguros"
  install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_GROUP}" "${CFG_DIR}"
  "${PYTHON_BIN}" - "$CFG_PATH" <<'PY'
import json
import os
import sys
from pathlib import Path

cfg_path = Path(sys.argv[1])
defaults = {
    "general": {
        "sound_enabled": True,
        "volume": 70,
        "tts_enabled": True,
    },
    "scale": {
        "port": "__dummy__",
        "baud": 115200,
        "hx711_dt": 5,
        "hx711_sck": 6,
        "calib_factor": 1.0,
        "smoothing": 5,
        "decimals": 0,
        "unit": "g",
        "ml_factor": 1.0,
    },
    "network": {
        "miniweb_enabled": True,
        "miniweb_port": 8080,
        "miniweb_pin": "",
    },
    "diabetes": {
        "diabetes_enabled": False,
        "ns_url": "",
        "ns_token": "",
        "hypo_alarm": 70,
        "hyper_alarm": 180,
        "mode_15_15": False,
        "insulin_ratio": 12.0,
        "insulin_sensitivity": 50.0,
        "target_glucose": 110,
    },
    "audio": {
        "audio_device": "default",
    },
}
cfg_path.write_text(json.dumps(defaults, indent=2), encoding="utf-8")
PY
  chown "${TARGET_USER}:${TARGET_GROUP}" "${CFG_PATH}" || true
fi

if [[ "${SKIP_INSTALL_ALL_PACKAGES:-0}" != "1" ]]; then
  apt-get update
  apt-get install -y --no-install-recommends \
    python3-venv python3-pip python3-dev \
    python3-tk \
    python3-picamera2 \
    libzbar0 \
    fonts-dejavu-core \
    network-manager \
    dnsutils curl jq
fi

if id "${TARGET_USER}" >/dev/null 2>&1; then
  if ! id -nG "${TARGET_USER}" | grep -qw dialout; then
    usermod -a -G dialout "${TARGET_USER}"
    echo "[info] Añadido ${TARGET_USER} a 'dialout' (se requiere reboot para aplicar)."
  fi
  if ! id -nG "${TARGET_USER}" | grep -qw video; then
    usermod -a -G video "${TARGET_USER}"
    echo "[info] Añadido ${TARGET_USER} a 'video'."
  fi
fi

install -d -m 0700 -o "${TARGET_USER}" -g "${TARGET_GROUP}" "${TARGET_HOME}/.config/bascula"
install -d -m 0775 -o root -g "${TARGET_GROUP}" /var/log/bascula

install -d -m 0755 /etc/default
if [[ ! -f /etc/default/bascula ]]; then
  cat <<EOF > /etc/default/bascula
# Paths OTA
BASCULA_PREFIX=/opt/bascula/current
BASCULA_VENV=/opt/bascula/current/.venv
# Puertos por defecto (mini-web prioriza BASCULA_MINIWEB_PORT)
BASCULA_MINIWEB_PORT=8080
BASCULA_WEB_PORT=8080
# Directorios de runtime/config
BASCULA_RUNTIME_DIR=/run/bascula
BASCULA_CFG_DIR=${TARGET_HOME}/.config/bascula
EOF
fi

BASCULA_ROOT="/opt/bascula"
BASCULA_RELEASES_DIR="${BASCULA_ROOT}/releases"
BASCULA_CURRENT_LINK="${BASCULA_ROOT}/current"
XWRAPPER="/etc/Xwrapper.config"
TMPFILES="/etc/tmpfiles.d/bascula.conf"
SAY_BIN="/usr/local/bin/say.sh"
MIC_TEST="/usr/local/bin/mic-test.sh"

HDMI_W="${HDMI_W:-1024}"
HDMI_H="${HDMI_H:-600}"
HDMI_FPS="${HDMI_FPS:-60}"

BOOTDIR="/boot/firmware"
[[ ! -d "${BOOTDIR}" ]] && BOOTDIR="/boot"
CONF="${BOOTDIR}/config.txt"

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
if [[ "${SKIP_INSTALL_ALL_PACKAGES:-0}" != "1" ]]; then
  apt-get update -y
  if [[ "${RUN_FULL_UPGRADE:-0}" = "1" ]]; then
    apt-get full-upgrade -y || true
  fi
  if [[ "${RUN_RPI_UPDATE:-0}" = "1" ]] && command -v rpi-update >/dev/null 2>&1; then
    SKIP_WARNING=1 rpi-update || true
  fi

  apt-get install -y git curl ca-certificates build-essential cmake pkg-config \
    python3 python3-venv python3-pip python3-dev python3-tk python3-numpy python3-serial \
    python3-pil.imagetk python3-xdg \
    x11-xserver-utils xserver-xorg xinit openbox \
    unclutter fonts-dejavu-core \
    libjpeg-dev zlib1g-dev libpng-dev \
    alsa-utils sox ffmpeg \
    libzbar0 gpiod python3-rpi.gpio \
    network-manager dnsutils jq sqlite3 tesseract-ocr tesseract-ocr-spa espeak-ng

  apt-get install -y xserver-xorg x11-xserver-utils xinit xserver-xorg-legacy unclutter \
                     libcamera-apps v4l-utils python3-picamera2
  apt-get install -y unclutter-startup || true
  echo "xserver-xorg-legacy xserver-xorg-legacy/allowed_users select Anybody" | debconf-set-selections
  DEBIAN_FRONTEND=noninteractive dpkg-reconfigure xserver-xorg-legacy || true
  echo "[info] Fase 1 completada. Recomendado 'sudo reboot' antes de continuar con Fase 2 si se añadieron grupos o overlays."
fi

# --- Audio defaults (ALSA / HifiBerry) ---
ALSA_CARD_ID=""
ALSA_CARD_DEV=""
ALSA_CARD_INDEX=""
ALSA_CARD_LABEL=""
SERVICE_USERS=()
AUDIO_USERS_WITH_HOME=()

if detect_playback_card; then
  log "[audio] selected card=${ALSA_CARD_ID} dev=${ALSA_CARD_DEV}"
  if ! write_global_asound "${ALSA_CARD_ID}" "${ALSA_CARD_DEV}"; then
    log "[audio] WARN global ALSA configuration failed (check permissions)"
  fi
  collect_service_users
  passwd_entry=""
  audio_home=""
  for audio_user in "${SERVICE_USERS[@]}"; do
    passwd_entry="$(getent passwd "${audio_user}" || true)"
    if [[ -z "${passwd_entry}" ]]; then
      log "[audio] WARN user=${audio_user} (passwd entry missing)"
      continue
    fi
    audio_home="$(printf '%s\n' "${passwd_entry}" | cut -d: -f6)"
    if [[ -z "${audio_home}" || ! -d "${audio_home}" ]]; then
      log "[audio] WARN user=${audio_user} (home not found)"
      continue
    fi
    write_user_asound "${audio_user}" "${ALSA_CARD_ID}" "${ALSA_CARD_DEV}" || true
    AUDIO_USERS_WITH_HOME+=("${audio_user}")
  done
  amixer_target="${ALSA_CARD_INDEX:-${ALSA_CARD_ID}}"
  if [[ -n "${amixer_target}" ]]; then
    amixer -c "${amixer_target}" sset Master 96% unmute >/dev/null 2>&1 || true
    amixer -c "${amixer_target}" sset Digital 96% unmute >/dev/null 2>&1 || true
    amixer -c "${amixer_target}" sset PCM 96% unmute >/dev/null 2>&1 || true
  fi
  alsactl store >/dev/null 2>&1 || true
  for audio_user in "${AUDIO_USERS_WITH_HOME[@]}"; do
    test_user_audio "${audio_user}" "${ALSA_CARD_ID}" "${ALSA_CARD_DEV}" || true
  done
else
  log "[audio] WARN no playback devices detected (aplay -l)"
fi

if (( WITH_PIPER_FLAG )); then
  voice_selftest || true
fi
# --- end Audio defaults ---


PYTHONPATH="${PROJECT_ROOT}" \
BASCULA_SETTINGS_DIR="${TARGET_HOME}/.bascula" \
BASCULA_MINIWEB_OWNER="${TARGET_USER}" \
BASCULA_MINIWEB_GROUP="${TARGET_GROUP}" \
"${PYTHON_BIN}" - <<'PY'
import os

from bascula.config.settings import Settings
from bascula.system.miniweb_pin import sync_miniweb_pin

settings = Settings.load()
sync_miniweb_pin(
    settings,
    owner=os.environ.get("BASCULA_MINIWEB_OWNER"),
    group=os.environ.get("BASCULA_MINIWEB_GROUP"),
)
PY

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
"${PYTHON_BIN}" - <<'PY' 2>/dev/null || true
try:
    from picamera2 import Picamera2
    print("Picamera2 OK")
except Exception as e:
    print(f"Picamera2 NO OK: {e}")
PY

# --- UART setup ---
if [[ "${PHASE:-all}" != "2" ]]; then
  bash "${SCRIPT_DIR}/fix-serial.sh"
  systemctl disable --now serial-getty@ttyAMA0.service serial-getty@ttyS0.service 2>/dev/null || true
  MODEL="$(tr -d '\0' </proc/device-tree/model 2>/dev/null || echo)"
  if ! echo "$MODEL" | grep -q "Raspberry Pi 5"; then
    if [[ -f "${CONF}" ]] && ! grep -q "^dtoverlay=disable-bt" "${CONF}"; then
      echo "dtoverlay=disable-bt" >> "${CONF}"
    fi
    systemctl disable --now hciuart 2>/dev/null || true
  fi

# Añade el usuario al grupo 'video' (acceso a /dev/video* y /dev/dri/*)
  if [[ "${SKIP_INSTALL_ALL_GROUPS:-0}" != "1" ]]; then
    for grp in video render input; do
      if ! getent group "$grp" >/dev/null 2>&1; then
        groupadd "$grp" || true
        log "Created missing group '$grp'"
      fi
    done

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
# --- Bascula-Cam (end) ---
EOF

  log "HDMI/KMS/I2S/PWM configured in ${CONF}"
fi


# --- EEPROM PSU_MAX_CURRENT ---
if [[ "${SKIP_INSTALL_ALL_EEPROM_CONFIG:-0}" != "1" ]]; then
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
fi

# --- Xwrapper ---
if [[ "${SKIP_INSTALL_ALL_XWRAPPER:-0}" != "1" ]]; then
  for config in "${XWRAPPER}" /etc/X11/Xwrapper.config; do
    install -D -m 0644 /dev/null "${config}"
    cat > "${config}" <<'EOF'
allowed_users=anybody
needs_root_rights=yes
EOF
  done
fi

chown root:root /usr/lib/xorg/Xorg || true
chmod 4755 /usr/lib/xorg/Xorg || true

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
    return u == "bascula-miniweb.service" || u == "bascula-app.service" || u == "ocr-service.service";
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
  readarray -t _WF < <("${PYTHON_BIN}" - <<'PY' 2>/dev/null || true
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
      readarray -t _WF < <("${PYTHON_BIN}" - "${WCONF}" <<'PY' 2>/dev/null || true
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
export PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_ROOT_USER_ACTION=ignore PIP_PREFER_BINARY=1
export PIP_INDEX_URL="https://www.piwheels.org/simple"
export PIP_EXTRA_INDEX_URL="https://pypi.org/simple"
echo "[inst] PIP_INDEX_URL=${PIP_INDEX_URL}"
if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi
VENV_DIR="${BASCULA_CURRENT_LINK}/.venv"
VENV_PY="${VENV_DIR}/bin/python"
VENV_PIP="${VENV_DIR}/bin/pip"

if [[ "${NET_OK}" = "1" ]]; then
  pip_retry "${VENV_PIP}" install --upgrade pip wheel setuptools
  pip_retry "${VENV_PIP}" install "numpy>=2.2,<2.3"
  if [[ -f "${BASCULA_CURRENT_LINK}/requirements.txt" ]]; then
    pip_retry "${VENV_PIP}" install -r "${BASCULA_CURRENT_LINK}/requirements.txt"
  fi
  pip_retry "${VENV_PIP}" install python-multipart || true
  pip_retry "${VENV_PIP}" install piper-tts || true
elif [[ -d "${OFFLINE_DIR}/wheels" ]]; then
  log "Installing venv dependencies from offline wheels (${OFFLINE_DIR}/wheels)"
  pip_retry "${VENV_PIP}" install --no-index --find-links "${OFFLINE_DIR}/wheels" --upgrade pip wheel setuptools || true
  pip_retry "${VENV_PIP}" install --no-index --find-links "${OFFLINE_DIR}/wheels" "numpy>=2.2,<2.3"
  if [[ -f "${BASCULA_CURRENT_LINK}/requirements.txt" ]]; then
    pip_retry "${VENV_PIP}" install --no-index --find-links "${OFFLINE_DIR}/wheels" -r "${BASCULA_CURRENT_LINK}/requirements.txt"
  fi
  pip_retry "${VENV_PIP}" install --no-index --find-links "${OFFLINE_DIR}/wheels" python-multipart || true
  pip_retry "${VENV_PIP}" install --no-index --find-links "${OFFLINE_DIR}/wheels" piper-tts || true
else
  warn "No network and no offline wheels: Skipping venv dependency installation"
fi

OCR_PY_PKGS=(pillow opencv-python-headless pytesseract rapidocr-onnxruntime)
if [[ "${NET_OK}" = "1" ]]; then
  pip_retry "${VENV_PIP}" install "${OCR_PY_PKGS[@]}"
elif [[ -d "${OFFLINE_DIR}/wheels" ]]; then
  pip_retry "${VENV_PIP}" install --no-index --find-links "${OFFLINE_DIR}/wheels" "${OCR_PY_PKGS[@]}"
else
  err "OCR dependencies (pillow/opencv-python-headless/pytesseract/rapidocr-onnxruntime) require Internet or offline wheels"
  exit 1
fi

if ! pip_retry "${VENV_PIP}" install --no-deps -e .; then
  err "Editable install of bascula package failed"
  exit 1
fi

if ! "${VENV_PIP}" check; then
  err "pip check detected dependency conflicts in the virtual environment"
  "${VENV_PIP}" freeze || true
  exit 1
fi

if [[ -x "${VENV_DIR}/bin/piper" ]] && ! command -v piper >/dev/null 2>&1; then
  ln -sf "${VENV_DIR}/bin/piper" /usr/local/bin/piper || true
fi
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

# 2) Reinstala simplejpeg preferentemente desde ruedas (piwheels)
"${VENV_PIP}" uninstall -y simplejpeg >/dev/null 2>&1 || true
if ! pip_retry "${VENV_PIP}" install "simplejpeg==1.8.2"; then
  pip_retry "${VENV_PIP}" install simplejpeg || true
fi

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


# Descarga voces desde cualquiera de los Releases del repositorio
GH_API="https://api.github.com/repos/DanielGTdiabetes/bascula-cam/releases"
GH_JSON="$(curl -fsSL "$GH_API" 2>/dev/null || true)"

voices=(
  es_ES-mls_10246-medium.onnx
  es_ES-mls_10246-medium.onnx.json
  es_ES-sharvard-medium.onnx
  es_ES-sharvard-medium.onnx.json
)

for f in "${voices[@]}"; do
  if [ ! -s "/opt/piper/models/$f" ]; then
    url="$(printf '%s' "$GH_JSON" | jq -r --arg N "$f" '.[]?.assets[]? | select(.name==$N) | .browser_download_url' 2>/dev/null | head -n1)"
    if [ -n "$url" ] && [ "$url" != "null" ]; then
      echo "  - $f"
      curl -fL --retry 4 --retry-delay 2 --continue-at - -o "/opt/piper/models/$f" "$url"
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

systemctl daemon-reload
systemctl reset-failed ocr-service.service 2>/dev/null || true
systemctl enable ocr-service.service
systemctl restart ocr-service.service
# --- end OCR deps hard-check ---

# --- PaddleOCR ---
if [[ "${INSTALL_PADDLEOCR:-0}" = "1" && "${NET_OK}" = "1" ]]; then
  PADDLE_VER_DEFAULT="2.6.2"
  PADDLE_VER="${PADDLE_VERSION:-${PADDLE_VER_DEFAULT}}"
  if ! "${VENV_PY}" -m pip install --no-cache-dir "paddlepaddle==${PADDLE_VER}"; then
    if ! "${VENV_PY}" -m pip install --no-cache-dir "paddlepaddle==2.6.1"; then
      if ! "${VENV_PY}" -m pip install --no-cache-dir "paddlepaddle==2.6.0"; then
        warn "PaddlePaddle ${PADDLE_VER} not available; trying latest."
        "${VENV_PY}" -m pip install --no-cache-dir paddlepaddle || warn "PaddlePaddle installation failed."
      fi
    fi
  fi
  if ! "${VENV_PY}" -m pip install --no-cache-dir paddleocr==2.7.0.3; then
    warn "PaddleOCR 2.7.0.3 not available; trying latest."
    "${VENV_PY}" -m pip install --no-cache-dir paddleocr || warn "PaddleOCR installation failed."
  fi
  "${VENV_PY}" -m pip install --no-cache-dir rapidocr-onnxruntime || true
elif [[ "${INSTALL_PADDLEOCR:-0}" = "1" ]]; then
  warn "No network: Skipping PaddlePaddle/PaddleOCR installation"
else
  log "Installing rapidocr-onnxruntime as PaddleOCR alternative"
  "${VENV_PIP}" install -q rapidocr-onnxruntime || true
fi

# --- Vision-lite (TFLite) ---
if [[ "${NET_OK}" = "1" ]]; then
  pip_retry "${VENV_PIP}" install -q --no-deps tflite-runtime==2.14.0 || true
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

if [[ "${SKIP_INSTALL_ALL_SERVICE_DEPLOY:-0}" != "1" ]]; then
  # --- AP fallback via systemd service ---
  install -D -m 0755 "${SCRIPT_DIR}/../scripts/net-fallback.sh" /opt/bascula/current/scripts/net-fallback.sh
  install -D -m 0644 "${SCRIPT_DIR}/../systemd/bascula-net-fallback.service" /etc/systemd/system/bascula-net-fallback.service

  # --- Mini-web service ---
  echo "[miniweb] preparando entorno…"
  install -d -m 0755 /opt/bascula/current
  MINIWEB_VENV="/opt/bascula/current/.venv"
  if [[ ! -d "${MINIWEB_VENV}" ]]; then
    python3 -m venv "${MINIWEB_VENV}"
  fi
  MINIWEB_PIP="${MINIWEB_VENV}/bin/pip"
  if [[ ! -x "${MINIWEB_PIP}" ]]; then
    err "pip del miniweb no encontrado en ${MINIWEB_PIP}"
    exit 1
  fi
  pip_retry "${MINIWEB_PIP}" install --upgrade pip wheel
  if [[ -f "/opt/bascula/current/requirements.txt" ]]; then
    pip_retry "${MINIWEB_PIP}" install -r "/opt/bascula/current/requirements.txt"
  fi
  if ! "${MINIWEB_PIP}" show fastapi >/dev/null 2>&1 || \
     ! "${MINIWEB_PIP}" show uvicorn >/dev/null 2>&1 || \
     ! "${MINIWEB_PIP}" show pydantic >/dev/null 2>&1; then
    pip_retry "${MINIWEB_PIP}" install fastapi 'uvicorn[standard]' pydantic || true
  fi

  install -D -m 0644 "${SCRIPT_DIR}/../systemd/bascula-miniweb.service" /etc/systemd/system/bascula-miniweb.service
  systemctl daemon-reload

  if systemctl list-unit-files bascula-web.service >/dev/null 2>&1; then
    systemctl disable --now bascula-web.service 2>/dev/null || true
  fi

  systemctl enable --now bascula-miniweb.service

  echo "[miniweb] health-check…"
  MINIWEB_PORT="$(resolve_miniweb_port)"
  miniweb_ok=0
  for i in $(seq 1 10); do
    if curl -fsS "http://127.0.0.1:${MINIWEB_PORT}/health" >/dev/null 2>&1; then
      echo "[miniweb] OK (port ${MINIWEB_PORT})"
      miniweb_ok=1
      break
    fi
    sleep 0.5
  done
  if [[ ${miniweb_ok} -ne 1 ]]; then
    err "[miniweb] ERROR: /health no responde tras 10 intentos"
    systemctl --no-pager -l status bascula-miniweb.service || true
    journalctl -u bascula-miniweb.service -n 120 --no-pager || true
    exit 1
  fi

  if command -v ufw >/dev/null 2>&1; then
    if ufw status | grep -q "Status: active"; then
      ufw allow 8080/tcp >/dev/null 2>&1 || true
    fi
  fi

  install -d -m 0700 -o "${TARGET_USER}" -g "${TARGET_GROUP}" "${TARGET_HOME}/.config/bascula" || true
  su -s /bin/bash -c 'mkdir -p ~/.config/bascula && chmod 700 ~/.config/bascula' "${TARGET_USER}" || true

  # --- UI service ---
  usermod -aG video,render,input "${TARGET_USER}" || true
  loginctl enable-linger "${TARGET_USER}" || true
  if [[ "${SKIP_INSTALL_ALL_X11_TMPFILES:-0}" != "1" ]]; then
    install -D -m 0644 "${SCRIPT_DIR}/../systemd/tmpfiles.d/bascula-x11.conf" /etc/tmpfiles.d/bascula-x11.conf
    systemd-tmpfiles --create /etc/tmpfiles.d/bascula-x11.conf || true
  fi

  install -D -m 0755 "${SCRIPT_DIR}/../scripts/xsession.sh" /opt/bascula/current/scripts/xsession.sh

  install -D -m 0755 -o "${TARGET_USER}" -g "${TARGET_GROUP}" /dev/stdin "${TARGET_HOME}/.xserverrc" <<'EOF'
#!/bin/sh
exec /usr/lib/xorg/Xorg.wrap :0 vt1
EOF
  install -D -m 0755 -o "${TARGET_USER}" -g "${TARGET_GROUP}" \
    "${SCRIPT_DIR}/../scripts/xinitrc.kiosk" "${TARGET_HOME}/.xinitrc"
  install -D -m 0755 -o "${TARGET_USER}" -g "${TARGET_GROUP}" \
    "${SCRIPT_DIR}/../scripts/openbox-autostart" "${TARGET_HOME}/.config/openbox/autostart"
  rm -f /usr/local/bin/bascula-app || true

  install -D -m 0644 -o root -g root /dev/stdin /etc/systemd/system/bascula-app.service <<'EOF'
[Unit]
Description=Bascula Digital Pro - UI (Xorg kiosk)
After=network-online.target
Wants=network-online.target
Conflicts=getty@tty1.service
Conflicts=bascula-recovery.service
StartLimitIntervalSec=120
StartLimitBurst=3

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/opt/bascula/current
Environment=HOME=/home/pi
Environment=USER=pi
Environment=XDG_RUNTIME_DIR=/run/user/1000
PermissionsStartOnly=yes
ExecStartPre=/usr/bin/install -d -m 0755 -o pi -g pi /var/log/bascula
ExecStartPre=/usr/bin/install -o pi -g pi -m 0644 /dev/null /var/log/bascula/app.log
# IMPORTANTE: no pasar -logfile ni -keeptty a Xorg
ExecStartPre=/usr/bin/install -d -m 0700 -o pi -g pi /home/pi/.local/share/xorg
ExecStart=/usr/bin/startx -- :0 vt1
Restart=on-failure
RestartSec=2
StandardOutput=journal
StandardError=journal
TTYPath=/dev/tty1
TTYReset=yes
TTYVHangup=yes

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable --now bascula-app.service

  install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_GROUP}" /etc/bascula
  install -m 0644 -o "${TARGET_USER}" -g "${TARGET_GROUP}" /dev/null /etc/bascula/APP_READY

  systemctl disable getty@tty1.service || true

  chown -R "${TARGET_USER}:${TARGET_GROUP}" "${TARGET_HOME}" || true
  systemctl enable --now bascula-net-fallback.service || true
fi

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

if "${VENV_PY}" - <<'PY'
import sys
try:
    import cv2  # noqa: F401
    import pytesseract  # noqa: F401
except Exception as exc:  # pragma: no cover - runtime check
    print(f"OCR_IMPORT_FAIL: {exc}", file=sys.stderr)
    sys.exit(1)
print("OCR_IMPORT_OK")
PY
then
  log "cv2+pytesseract: OK"
else
  err "OCR dependencies missing (cv2/pytesseract). Check virtualenv installation."
  exit 1
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
PORT="$(resolve_miniweb_port)"
for i in {1..20}; do
  if curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    log "Mini-web service: OK (port ${PORT})"
    break
  fi
  sleep 0.5
done
if ! curl -fsS "http://127.0.0.1:${PORT}/health" >/dev/null; then
  journalctl -u bascula-miniweb.service -n 200 --no-pager || true
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
  warn "Overlay PWM: Presente en ${CONF} (puede interferir con I2S, revisar configuración)"
else
  log "Overlay PWM: No presente en ${CONF} (compatible con DAC I2S)"
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

# --- Optional extras (Piper) ---
if (( WITH_PIPER_FLAG )); then
  log "Instalando extras (--with-piper)"
  WITH_PIPER=1 bash "${SCRIPT_DIR}/install-3-extras.sh"
else
  log "Extras opcionales omitidos (use --with-piper para habilitarlos)"
fi

# --- UI verification (startx via systemd) ---
sleep 3
if ! systemctl is-active --quiet bascula-app.service; then
  journalctl -u bascula-app -n 300 --no-pager || true
  tail -n 160 "/home/pi/.local/share/xorg/Xorg.0.log" 2>/dev/null || true
  echo "[ERR] bascula-app no ha arrancado" >&2
  exit 1
fi

pgrep -af "Xorg|startx" >/dev/null || { echo "[ERR] Xorg no está corriendo"; exit 1; }
pgrep -af "python .*bascula.ui.app" >/dev/null || { echo "[ERR] UI no detectada"; exit 1; }

echo "[OK] Mini-web y UI operativos"

# --- Final message ---
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo "----------------------------------------------------"
echo "Installation completed."
echo "Logs: /var/log/bascula"
echo "Active release: ${BASCULA_CURRENT_LINK}"
echo "Mini-web: http://${IP:-<IP>}:${PORT}/"
echo "OCR: http://127.0.0.1:8078/ocr"
echo "AP: SSID=${AP_SSID} PASS=${AP_PASS} IFACE=${AP_IFACE} profile=${AP_NAME}"
echo "Reboot to apply overlays: sudo reboot"
echo "Manual UI test: sudo -u ${TARGET_USER} startx -- vt1"
echo "Cómo verificar:"
echo "  aplay -l"
echo "  aplay -L | sed -n '1,40p'"
echo "  speaker-test -c2 -twav -l1"
echo "  sudo -u pi -H bash -lc 'speaker-test -c2 -twav -l1'"
if [[ -n "${ALSA_CARD_ID}" && -n "${ALSA_CARD_DEV}" ]]; then
  echo "Si falla: prueba 'aplay -D hw:${ALSA_CARD_ID},${ALSA_DEV} /usr/share/sounds/alsa/Front_Center.wav'"
fi
if command -v /usr/local/bin/say.sh >/dev/null 2>&1; then
  /usr/local/bin/say.sh "Instalacion correcta" >/dev/null 2>&1 || true
elif command -v espeak-ng >/dev/null 2>&1; then
  espeak-ng -v es -s 170 "Instalacion correcta" >/dev/null 2>&1 || true
fi

#!/usr/bin/env bash
: "${TARGET_USER:=pi}"
: "${FORCE_INSTALL_PACKAGES:=0}"

set -euxo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ "${BASCULA_CI:-0}" == "1" ]]; then
  export DESTDIR="${DESTDIR:-/tmp/ci-root}"
  mock_systemctl="${SYSTEMCTL:-${ROOT_DIR}/ci/mocks/systemctl}"
  if [[ -x "${mock_systemctl}" ]]; then
    export SYSTEMCTL="${mock_systemctl}"
  else
    export SYSTEMCTL="${SYSTEMCTL:-/bin/systemctl}"
  fi
else
  export SYSTEMCTL="${SYSTEMCTL:-/bin/systemctl}"
fi

SYSTEMCTL_BIN="${SYSTEMCTL}"

run_systemctl() {
  "${SYSTEMCTL_BIN}" "$@"
}

resolve_boot_path() {
  local dest="$1"
  if [[ -n "${dest}" ]]; then
    printf '%s' "${dest%/}/boot"
  else
    printf '%s' "/boot"
  fi
}

apply_uart() {
  local dest_root="${1:-}"
  local boot_dir
  boot_dir="$(resolve_boot_path "${dest_root}")"

  local cfg
  local candidates=()
  if [[ -n "${dest_root}" ]]; then
    candidates+=("${boot_dir}/config.txt" "${boot_dir}/firmware/config.txt")
  else
    candidates+=("/boot/firmware/config.txt" "/boot/config.txt")
  fi

  for candidate in "${candidates[@]}"; do
    if [[ -f "${candidate}" ]]; then
      cfg="${candidate}"
      break
    fi
  done

  if [[ -z "${cfg:-}" ]]; then
    cfg="${candidates[0]}"
    install -d -m 0755 "$(dirname "${cfg}")"
    : >"${cfg}"
  fi

  python3 - "${cfg}" <<'PYTHON'
import pathlib
import sys

cfg_path = pathlib.Path(sys.argv[1])
cfg_path.parent.mkdir(parents=True, exist_ok=True)
original = cfg_path.read_text() if cfg_path.exists() else ""
lines = original.splitlines()

def upsert(key, value):
    target = f"{key}={value}"
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(f"{key}="):
            lines[idx] = target
            break
    else:
        lines.append(target)

upsert("enable_uart", "1")
if not any(line.strip() == "dtoverlay=disable-bt" for line in lines):
    lines.append("dtoverlay=disable-bt")

cfg_path.write_text("\n".join(lines) + "\n")
PYTHON

  local cmdline_candidates=()
  if [[ -n "${dest_root}" ]]; then
    cmdline_candidates+=("${boot_dir}/firmware/cmdline.txt" "${boot_dir}/cmdline.txt")
  else
    cmdline_candidates+=("/boot/firmware/cmdline.txt" "/boot/cmdline.txt")
  fi

  local cmdline_file=""
  for candidate in "${cmdline_candidates[@]}"; do
    if [[ -f "${candidate}" ]]; then
      cmdline_file="${candidate}"
      break
    fi
  done

  if [[ -n "${cmdline_file}" ]]; then
    python3 - "${cmdline_file}" <<'PYTHON'
import pathlib
import sys

cmdline_path = pathlib.Path(sys.argv[1])
original = cmdline_path.read_text()
tokens = original.strip().split()
filtered = [
    token
    for token in tokens
    if token not in {"console=serial0,115200", "console=ttyAMA0,115200"}
]
newline = "\n" if original.endswith("\n") else ""
cmdline_path.write_text(" ".join(filtered) + newline)
PYTHON
  fi

  local svc
  for svc in hciuart.service serial-getty@serial0.service serial-getty@ttyAMA0.service serial-getty@ttyS0.service; do
    run_systemctl disable --now "${svc}" 2>/dev/null || true
  done
}

render_x735_poweroff_service() {
  local dest_root="${1:-}"
  local threshold="${2:-${X735_POWER_OFF_MV:-5000}}"
  local service_dir
  if [[ -n "${dest_root}" ]]; then
    service_dir="${dest_root%/}/etc/systemd/system"
  else
    service_dir="/etc/systemd/system"
  fi
  install -d -m 0755 "${service_dir}"
  cat >"${service_dir}/x735-poweroff.service" <<UNIT
[Unit]
Description=x735 Safe Poweroff Monitor
After=multi-user.target

[Service]
Type=simple
User=root
ExecStart=/usr/bin/python3 /opt/x735/x735-poweroff.py --threshold ${threshold}
Restart=always
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
UNIT
}

if [[ "${1:-}" == "--apply-uart" ]]; then
  shift
  apply_uart "${DESTDIR:-}"
  exit 0
fi

if [[ "${1:-}" == "--render-x735-service" ]]; then
  shift
  render_x735_poweroff_service "${DESTDIR:-}" "${1:-}"
  exit 0
fi

if [[ "${BASCULA_CI:-0}" == "1" ]]; then
  install -d -m 0755 "${DESTDIR}/var/lib/bascula"
  install -d -m 0755 "${DESTDIR}/etc"
  install -d -m 0755 "${DESTDIR}/etc/systemd/system"
  printf 'ok\n' > "${DESTDIR}/var/lib/bascula/install-1.done"
  echo "[OK] install-1-system (CI)"
  exit 0
fi

apt_has_package() {
  if apt-cache --quiet=2 show "$1" >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

resolve_package() {
  for candidate in "$@"; do
    if apt_has_package "${candidate}"; then
      echo "${candidate}"
      return 0
    fi
  done

  echo "[ERROR] Ninguno de los paquetes está disponible: $*" >&2
  exit 1
}

MARKER="/var/lib/bascula/install-1.done"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  exec sudo TARGET_USER="${TARGET_USER}" FORCE_INSTALL_PACKAGES="${FORCE_INSTALL_PACKAGES}" bash "$0" "$@"
fi

TARGET_USER="${TARGET_USER:-${SUDO_USER:-pi}}"
TARGET_GROUP="$(id -gn "${TARGET_USER}" 2>/dev/null || echo "${TARGET_USER}")"
export DEBIAN_FRONTEND=noninteractive

# Parte 1 SIEMPRE instala paquetes base en limpias
# (no usar SKIP_INSTALL_ALL_PACKAGES aquí)
apt-get update

# Paquetes base del sistema (toolchain, python build, OCR, X, cámara, audio, red, utilidades)
DEPS=(
  # UI/X
  xserver-xorg x11-xserver-utils xinit xserver-xorg-legacy unclutter
  python3-tk
  mesa-utils "$(resolve_package libegl1 libegl1-mesa)" "$(resolve_package libgles2 libgles2-mesa)" \
    fonts-dejavu "$(resolve_package fonts-freefont-ttf fonts-freefont)"
  # Cámara
  "$(resolve_package libcamera-apps libcamera-apps-lite)" python3-picamera2 v4l-utils
  # Audio
  alsa-utils
  # OCR / visión
  tesseract-ocr libtesseract-dev libleptonica-dev tesseract-ocr-spa tesseract-ocr-eng
  # ZBar (QR/Barcodes si la app lo usa)
  "$(resolve_package libzbar0 libzbar1)" zbar-tools
  # Python build
  python3-venv python3-pip python3-dev build-essential libffi-dev zlib1g-dev \
  libjpeg62-turbo-dev libopenjp2-7 libopenjp2-7-dev libtiff-dev libatlas-base-dev \
  libfreetype6-dev liblcms2-dev libwebp-dev libwebpdemux2 tcl-dev tk-dev \
  python3-rpi.gpio
  # Red
  network-manager rfkill
  # Miscelánea / CLI
  curl git jq usbutils pciutils rsync
  # EEPROM (bloqueada en critical)
  rpi-eeprom
)

MISSING_DEPS=()
for package in "${DEPS[@]}"; do
  if ! apt_has_package "${package}"; then
    MISSING_DEPS+=("${package}")
  fi
done

if ((${#MISSING_DEPS[@]})); then
  echo "[ERROR] No se pudieron localizar los siguientes paquetes: ${MISSING_DEPS[*]}" >&2
  exit 1
fi

apt-get install -y "${DEPS[@]}"

echo "xserver-xorg-legacy xserver-xorg-legacy/allowed_users select Anybody" | debconf-set-selections
DEBIAN_FRONTEND=noninteractive dpkg-reconfigure xserver-xorg-legacy || true

run_systemctl enable NetworkManager || true
run_systemctl restart NetworkManager || true

# Reglas Polkit para permitir gestión de Wi-Fi y servicios Bascula
install -d -m 0755 /etc/polkit-1/rules.d
cat > /etc/polkit-1/rules.d/50-bascula-nm.rules <<EOF
polkit.addRule(function(action, subject) {
  function allowed() {
    return subject.user == "${TARGET_USER}" || subject.isInGroup("${TARGET_GROUP}");
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
  function allowedUnit(u) {
    return typeof u === "string" && u.indexOf("bascula-") === 0;
  }
  if ((subject.user == "${TARGET_USER}" || subject.isInGroup("${TARGET_GROUP}")) &&
      (id == "org.freedesktop.systemd1.manage-units" ||
       id == "org.freedesktop.systemd1.restart-unit" ||
       id == "org.freedesktop.systemd1.start-unit" ||
       id == "org.freedesktop.systemd1.stop-unit") &&
      allowedUnit(unit)) {
    return polkit.Result.YES;
  }
});
EOF
run_systemctl restart polkit NetworkManager || true

# Configuración de UART estable para ESP32 en /dev/serial0
CMDLINE_FILE="/boot/firmware/cmdline.txt"
if [[ -f "${CMDLINE_FILE}" ]]; then
  python3 - "$CMDLINE_FILE" <<'PYTHON'
import pathlib
import sys

cmdline_path = pathlib.Path(sys.argv[1])
original = cmdline_path.read_text()
tokens = original.strip().split()
filtered = [
    token
    for token in tokens
    if token not in {"console=serial0,115200", "console=ttyAMA0,115200"}
]
if filtered != tokens:
    newline = "\n" if original.endswith("\n") else ""
    cmdline_path.write_text(" ".join(filtered) + newline)
PYTHON
fi

apply_uart ""
usermod -aG dialout "${TARGET_USER}" || true

echo "[OK] UART activado para ESP32 en /dev/serial0"

# Polkit para permitir shared/system changes al grupo netdev
if [[ -f "${ROOT_DIR}/scripts/polkit/10-nm-shared.pkla" ]]; then
  install -m 0644 -o root -g root "${ROOT_DIR}/scripts/polkit/10-nm-shared.pkla" \
    /etc/polkit-1/localauthority/50-local.d/10-nm-shared.pkla
  usermod -aG netdev "${TARGET_USER}" || true
fi

# ------------------------------------------------------------------
#  [OPCIONAL] HAT Geekworm x735 v3: fan + poweroff (umbral 5000 mV)
#  Activar con BASCULA_ENABLE_X735=1
# ------------------------------------------------------------------
if [[ "${BASCULA_ENABLE_X735:-0}" == "1" ]]; then
  echo "[x735] Instalando soporte x735 v3 (fan + poweroff)"
  X735_DIR="/opt/x735"
  install -d -m 0755 "${X735_DIR}"
  chown -R "${TARGET_USER}:${TARGET_GROUP}" "${X735_DIR}"

  # Si se optase por User=pi, habilitar sudo sin contraseña para poweroff:
  # echo "pi ALL=(root) NOPASSWD:/sbin/poweroff" | sudo tee /etc/sudoers.d/x735-poweroff
  # chmod 440 /etc/sudoers.d/x735-poweroff

  if [[ ! -d "${X735_DIR}/repo/.git" ]]; then
    sudo -u "${TARGET_USER}" git clone --depth=1 https://github.com/geekworm-com/x735-v3.0 "${X735_DIR}/repo"
  else
    sudo -u "${TARGET_USER}" git -C "${X735_DIR}/repo" pull --ff-only || true
  fi

  install -m 0755 "${X735_DIR}/repo/fan/x735pwm.py" "${X735_DIR}/x735pwm.py"
  install -m 0755 "${X735_DIR}/repo/poweroff/x735-poweroff.py" "${X735_DIR}/x735-poweroff.py"

  cat >/etc/default/x735 <<'EOF'
# Habilitar/ajustar comportamiento del HAT x735
X735_POWER_OFF_MV=5000        # umbral mV para apagado seguro
X735_FAN_MIN_PWM=60           # PWM mínimo (0-100)
X735_FAN_TEMP_ON=55           # °C encendido
X735_FAN_TEMP_OFF=48          # °C apagado
EOF

  if [[ -f "${X735_DIR}/x735-poweroff.py" ]] && grep -q 'POWER_OFF_VOLTAGE' "${X735_DIR}/x735-poweroff.py"; then
    sed -i -E 's/^(POWER_OFF_VOLTAGE\s*=\s*)[0-9]+/\1 5000/' "${X735_DIR}/x735-poweroff.py"
  fi

  cat >/etc/systemd/system/x735-fan.service <<UNIT
[Unit]
Description=x735 Fan Control
After=multi-user.target

[Service]
Type=simple
EnvironmentFile=-/etc/default/x735
ExecStart=/bin/bash -lc "/usr/bin/python3 /opt/x735/x735pwm.py --min-pwm \"\${X735_FAN_MIN_PWM:-60}\" --ton \"\${X735_FAN_TEMP_ON:-55}\" --toff \"\${X735_FAN_TEMP_OFF:-48}\""
Restart=always
User=${TARGET_USER}
Group=${TARGET_GROUP}

[Install]
WantedBy=multi-user.target
UNIT

  render_x735_poweroff_service "" "${X735_POWER_OFF_MV:-5000}"

  run_systemctl daemon-reload
  run_systemctl enable --now x735-fan.service x735-poweroff.service
  echo "[x735] Servicios habilitados: x735-fan.service, x735-poweroff.service"
else
  echo "[x735] Omitido (BASCULA_ENABLE_X735!=1)"
fi

# Xwrapper: permitir X como usuario normal (ambas rutas por compatibilidad)
for config in /etc/Xwrapper.config /etc/X11/Xwrapper.config; do
  install -D -m 0644 /dev/null "${config}"
  cat >"${config}" <<'EOCONF'
allowed_users=anybody
needs_root_rights=yes
EOCONF
done

chown root:root /usr/lib/xorg/Xorg || true
chmod 4755 /usr/lib/xorg/Xorg || true

# tmpfiles: socket X por boot
install -D -m 0644 "${ROOT_DIR}/systemd/tmpfiles.d/bascula-x11.conf" /etc/tmpfiles.d/bascula-x11.conf
systemd-tmpfiles --create /etc/tmpfiles.d/bascula-x11.conf || systemd-tmpfiles --create || true

# Grupos: GPU/entrada
getent group render >/dev/null || groupadd render
usermod -aG video,render,input "${TARGET_USER}" || true

# EEPROM conservadora
install -D -m 0644 /dev/null /etc/default/rpi-eeprom-update
cat >/etc/default/rpi-eeprom-update <<'EOEEPROM'
FIRMWARE_RELEASE_STATUS="critical"
EOEEPROM
apt-mark hold rpi-eeprom || true

# (P1) Configurar AP de NetworkManager ahora para permitir onboarding tras Fase 1
bash "${SCRIPT_DIR}/setup_ap_nm.sh" || true

# Marca de fin de parte 1
install -d -m 0755 /var/lib/bascula
echo ok > "${MARKER}"
echo "[INFO] Parte 1 completada. Reinicia ahora."

#!/usr/bin/env bash
:"${TARGET_USER:=pi}"
:"${FORCE_INSTALL_PACKAGES:=0}"

set -euo pipefail
IFS=$'\n\t'

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

reset_pwm_channels() {
  local chip_dir pwm_dir pwm_num
  for chip_dir in /sys/class/pwm/pwmchip*; do
    [[ -d "${chip_dir}" ]] || continue
    for pwm_dir in "${chip_dir}"/pwm*; do
      [[ -d "${pwm_dir}" ]] || continue
      pwm_num="${pwm_dir##*pwm}"
      if [[ -n "${pwm_num}" ]]; then
        printf '%s\n' "${pwm_num}" >"${chip_dir}/unexport" 2>/dev/null || true
      fi
    done
  done
}

resolve_boot_path() {
  local dest="$1"
  if [[ -n "${dest}" ]]; then
    printf '%s' "${dest%/}/boot"
  else
    printf '%s' "/boot"
  fi
}

locate_boot_config() {
  local dest_root="$1"
  local boot_dir
  boot_dir="$(resolve_boot_path "${dest_root}")"
  local candidates=()
  if [[ -n "${dest_root}" ]]; then
    candidates+=("${boot_dir}/config.txt" "${boot_dir}/firmware/config.txt")
  else
    candidates+=("/boot/firmware/config.txt" "/boot/config.txt")
  fi

  for candidate in "${candidates[@]}"; do
    if [[ -f "${candidate}" ]]; then
      printf '%s' "${candidate}"
      return 0
    fi
  done

  printf '%s' "${candidates[0]}"
}

configure_boot_firmware() {
  local dest_root="${1:-}"
  local cfg
  cfg="$(locate_boot_config "${dest_root}")"
  install -d -m 0755 "$(dirname "${cfg}")"
  : >>"${cfg}"

  python3 - "${cfg}" <<'PYTHON'
import pathlib
import sys

cfg_path = pathlib.Path(sys.argv[1])
content = cfg_path.read_text()
lines = [line.rstrip("\n") for line in content.splitlines()]

def remove_with_prefix(items, prefix):
    return [line for line in items if not line.strip().startswith(prefix)]

lines = remove_with_prefix(lines, "enable_uart=")
lines = remove_with_prefix(lines, "dtparam=i2c_arm=")

LEGACY = {
    "dtoverlay=pi3-miniuart-bt",
    "dtoverlay=miniuart-bt",
}
lines = [line for line in lines if line.strip() not in LEGACY]

lines = [line for line in lines if line.strip() != "dtoverlay=disable-bt"]

if "enable_uart=1" not in lines:
    lines.append("enable_uart=1")

if "dtparam=i2c_arm=on" not in lines:
    lines.append("dtparam=i2c_arm=on")

if "dtoverlay=disable-bt" not in lines:
    lines.append("dtoverlay=disable-bt")

cfg_path.write_text("\n".join(lines) + ("\n" if lines else ""))
PYTHON

  sed -i '/^dtoverlay=max98357a/d' "${cfg}"
  printf 'dtoverlay=max98357a,audio=on\n' >>"${cfg}"

  local cmdline_candidates=()
  local boot_dir
  boot_dir="$(resolve_boot_path "${dest_root}")"
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

  if [[ -f "${cfg}" ]]; then
    sed -i '/# --- Bascula-Cam (Pi 5): Video + Audio I2S + PWM ---/,/# --- Bascula-Cam (end) ---/d' "${cfg}"
    cat >>"${cfg}" <<'EOF'
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
  fi
}

if [[ "${BASCULA_CI:-0}" == "1" ]]; then
  install -d -m 0755 "${DESTDIR}/var/lib/bascula"
  install -d -m 0755 "${DESTDIR}/etc"
  install -d -m 0755 "${DESTDIR}/etc/systemd/system"
  rm -rf "${DESTDIR}/opt/bascula"
  install -d -m 0755 "${DESTDIR}/opt/bascula/current"
  install -d -m 0755 "${DESTDIR}/opt/bascula/shared/userdata"
  printf 'ok\n' > "${DESTDIR}/var/lib/bascula/install-1.done"
  echo "[OK] install-1-system (CI)"
  exit 0
fi

STATE_DIR="${DESTDIR:-}/var/lib/bascula"
MARKER="${STATE_DIR}/install-1.done"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  exec sudo TARGET_USER="${TARGET_USER}" FORCE_INSTALL_PACKAGES="${FORCE_INSTALL_PACKAGES}" bash "$0" "$@"
fi

TARGET_USER="${TARGET_USER:-${SUDO_USER:-pi}}"
TARGET_GROUP="$(id -gn "${TARGET_USER}" 2>/dev/null || echo "${TARGET_USER}")"
export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends \
  python3-venv python3-pip python3-tk \
  python3-libcamera python3-picamera2 libcamera-tools \
  i2c-tools libcap-dev curl jq \
  alsa-utils sox espeak-ng libasound2-dev piper \
  xserver-xorg xinit openbox x11-xserver-utils unclutter \
  libzbar0 network-manager

install -d -m 0755 "${DESTDIR:-}/etc/bascula"
install -m 0755 "${ROOT_DIR}/scripts/xsession.sh" "${DESTDIR:-}/etc/bascula/xsession.sh"
cat <<'EOF' > "${DESTDIR:-}/etc/bascula/xserverrc"
exec /usr/lib/xorg/Xorg :0 vt1 -nolisten tcp -noreset
EOF
chmod 0755 "${DESTDIR:-}/etc/bascula/xserverrc"

run_systemctl enable --now NetworkManager.service || true
run_systemctl disable --now dhcpcd.service 2>/dev/null || true
run_systemctl disable --now wpa_supplicant.service 2>/dev/null || true

configure_boot_firmware "${DESTDIR:-}"

for svc in serial-getty@serial0.service serial-getty@ttyAMA0.service; do
  run_systemctl disable "${svc}" 2>/dev/null || true
  run_systemctl stop "${svc}" 2>/dev/null || true
done

for svc in hciuart.service bluetooth.service; do
  run_systemctl disable --now "${svc}" 2>/dev/null || true
done

udev_rules_dir="${DESTDIR:-}/etc/udev/rules.d"
install -d -m 0755 "${udev_rules_dir}"
cat > "${udev_rules_dir}/60-serial0.rules" <<'EOF'
KERNEL=="ttyAMA[0-9]*", SYMLINK+="serial0"
KERNEL=="ttyS[0-9]*",   SYMLINK+="serial0"
EOF

if [[ -z "${DESTDIR:-}" ]]; then
  install -d -m 0755 /opt
  if [[ -d /opt/x735-script && ! -d /opt/x735-script/.git ]]; then
    mv "/opt/x735-script" "/opt/x735-script.bak.$(date +%s)" || true
  fi
  if [[ ! -d /opt/x735-script ]]; then
    git clone https://github.com/geekworm-com/x735-script /opt/x735-script || true
  else
    git -C /opt/x735-script pull --ff-only || true
  fi

  if [[ -d /opt/x735-script ]]; then
    pushd /opt/x735-script >/dev/null
    chmod +x *.sh || true
    sed -i 's/pwmchip0/pwmchip2/g' x735-fan.sh 2>/dev/null || true
    reset_pwm_channels
    ./install-fan-service.sh || true
    ./install-pwr-service.sh || true
    popd >/dev/null

    if [[ ! -f /etc/systemd/system/x735-fan.service || ! -f /etc/systemd/system/x735-pwr.service ]]; then
      echo "[WARN] x735 services not installed correctly" >&2
    fi

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

    install -d -m 0755 /usr/local/sbin
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

for chip in /sys/class/pwm/pwmchip*; do
  [[ -d "${chip}" ]] || continue
  for pwm in "${chip}"/pwm*; do
    [[ -d "${pwm}" ]] || continue
    num="${pwm##*pwm}"
    if [[ -n "${num}" ]]; then
      printf '%s\n' "${num}" >"${chip}/unexport" 2>/dev/null || true
    fi
  done
done

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

    run_systemctl daemon-reload
    run_systemctl enable --now x735-fan.service x735-pwr.service 2>/dev/null || true
    run_systemctl enable --now x735-ensure.service 2>/dev/null || true

    if command -v systemd-analyze >/dev/null 2>&1; then
      units_to_verify=()
      for unit in x735-fan.service x735-pwr.service x735-ensure.service; do
        if [[ -f "/etc/systemd/system/${unit}" ]]; then
          units_to_verify+=("/etc/systemd/system/${unit}")
        fi
      done
      if (( ${#units_to_verify[@]} > 0 )); then
        systemd-analyze verify "${units_to_verify[@]}" || true
      fi
      unset units_to_verify || true
    fi

    if command -v journalctl >/dev/null 2>&1 && \
       journalctl -u x735-fan.service -n 20 --no-pager 2>/dev/null | grep -q 'Device or resource busy'; then
      reset_pwm_channels
      run_systemctl restart x735-fan.service 2>/dev/null || true
    fi

    for svc in x735-fan.service x735-pwr.service; do
      if ! run_systemctl is-active "${svc}" >/dev/null 2>&1; then
        run_systemctl restart "${svc}" 2>/dev/null || true
      fi
      if ! run_systemctl is-active "${svc}" >/dev/null 2>&1; then
        echo "[WARN] ${svc} is not active" >&2
      fi
    done

    if command -v journalctl >/dev/null 2>&1 && \
       journalctl -u x735-fan.service -n 20 --no-pager 2>/dev/null | grep -q 'Device or resource busy'; then
      echo "[WARN] x735-fan.service reported 'Device or resource busy'" >&2
    fi

    run_systemctl disable --now x735-poweroff.service 2>/dev/null || true
  fi
fi

if [[ -z "${DESTDIR:-}" ]] && command -v udevadm >/dev/null 2>&1; then
  udevadm control --reload || true
  udevadm trigger --subsystem-match=tty || true
fi

getent group render >/dev/null || groupadd render
usermod -aG dialout,tty,video,render,input "${TARGET_USER}" || true

install -d -m 0755 "${STATE_DIR}"
echo ok > "${MARKER}"
echo "[inst] UART configurado. Reboot requerido para aplicar dtoverlay=disable-bt"
echo "[INFO] Parte 1 completada. Reinicia ahora."

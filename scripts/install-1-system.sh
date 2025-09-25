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

write_file_if_changed() {
  local path="$1"
  local content="$2"
  local mode="${3:-0644}"
  local dir
  dir="$(dirname "${path}")"
  install -d -m 0755 "${dir}"
  local tmp
  tmp="$(mktemp)"
  printf '%s' "${content}" >"${tmp}"
  if [[ ! -f "${path}" ]] || ! cmp -s "${tmp}" "${path}"; then
    install -m "${mode}" "${tmp}" "${path}"
  fi
  rm -f "${tmp}"
}

detect_kms_card() {
  if [[ -n "${DESTDIR:-}" ]]; then
    printf '%s' 'card1'
    return 0
  fi

  local drm_root="/sys/class/drm"
  local status_file card=""
  for status_file in "${drm_root}"/card*-HDMI-A-*/status; do
    [[ -f "${status_file}" ]] || continue
    if [[ "$(<"${status_file}")" == "connected" ]]; then
      card="${status_file%/HDMI-A-*}"
      card="${card##*/}"
      break
    fi
  done

  if [[ -z "${card}" ]]; then
    if [[ -e "${drm_root}/card1" ]]; then
      card='card1'
    elif [[ -e "${drm_root}/card0" ]]; then
      card='card0'
    else
      card='card1'
    fi
  fi

  printf '%s' "${card}"
}

configure_modesetting() {
  local dest_root="${DESTDIR:-}"
  local kms_card
  kms_card="$(detect_kms_card)"
  local kmsdev="/dev/dri/${kms_card}"
  local conf_path="${dest_root%/}/etc/X11/xorg.conf.d/20-modesetting.conf"
  local content
  read -r -d '' content <<'EOF'
Section "Device"
  Identifier "GPU0"
  Driver "modesetting"
  Option "PrimaryGPU" "true"
  Option "kmsdev" "${kmsdev}"
EndSection
EOF
  write_file_if_changed "${conf_path}" "${content}\n"
}

ensure_xwrapper_config() {
  local dest_root="${DESTDIR:-}"
  local wrapper_path="${dest_root%/}/etc/X11/Xwrapper.config"
  local content=$'allowed_users=anybody\nneeds_root_rights=yes\n'
  write_file_if_changed "${wrapper_path}" "${content}"
}

set_xorg_wrap_permissions() {
  local dest_root="${DESTDIR:-}"
  local target="${dest_root%/}/usr/lib/xorg/Xorg.wrap"
  if [[ -f "${target}" ]]; then
    chmod 6755 "${target}" || true
  fi
}


setup_x735_services() {
  local dest_root="${DESTDIR:-}"
  local bin_dir="${dest_root%/}/usr/local/bin"
  local unit_dir="${dest_root%/}/etc/systemd/system"

  install -d -m 0755 "${bin_dir}"
  install -m 0755 "${ROOT_DIR}/overlay/x735/x735-fan.sh" "${bin_dir}/x735-fan"
  install -m 0755 "${ROOT_DIR}/overlay/x735/x735-poweroff.sh" "${bin_dir}/x735-poweroff"

  install -d -m 0755 "${unit_dir}"
  install -m 0644 "${ROOT_DIR}/systemd/x735-fan.service" "${unit_dir}/x735-fan.service"
  install -m 0644 "${ROOT_DIR}/systemd/x735-poweroff.service" "${unit_dir}/x735-poweroff.service"

  if [[ -z "${dest_root}" ]]; then
    run_systemctl daemon-reload || true
    local services=(x735-fan.service x735-poweroff.service)
    local svc
    for svc in "${services[@]}"; do
      if ! run_systemctl enable --now "${svc}"; then
        echo "[WARN] Failed to enable ${svc}" >&2
      fi
    done
    for svc in "${services[@]}"; do
      if ! run_systemctl is-active "${svc}" >/dev/null 2>&1; then
        echo "[WARN] ${svc} is not active" >&2
      fi
    done
  fi
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
  local cfg_dir
  cfg_dir="$(dirname "${cfg}")"
  install -d -m 0755 "${cfg_dir}"

  local backup="${cfg}.bak"
  if [[ -f "${cfg}" && ! -f "${backup}" ]]; then
    cp -a "${cfg}" "${backup}"
  fi

  : >>"${cfg}"
  python3 "${ROOT_DIR}/tools/update-config.py" "${cfg}"

  local boot_dir
  boot_dir="$(resolve_boot_path "${dest_root}")"
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
  xserver-xorg xserver-xorg-legacy xinit openbox x11-xserver-utils unclutter \
  libzbar0 network-manager gpiod libgpiod-tools

if dpkg -l xserver-xorg-video-fbdev >/dev/null 2>&1; then
  apt-get purge -y xserver-xorg-video-fbdev || true
fi

ensure_xwrapper_config
configure_modesetting
set_xorg_wrap_permissions


install -d -m 0755 "${DESTDIR:-}/etc/bascula"
install -m 0755 "${ROOT_DIR}/scripts/xsession.sh" "${DESTDIR:-}/etc/bascula/xsession.sh"
cat <<'EOF' > "${DESTDIR:-}/etc/bascula/xserverrc"
exec /usr/lib/xorg/Xorg.wrap :0 vt1 -nolisten tcp -noreset
EOF
chmod 0755 "${DESTDIR:-}/etc/bascula/xserverrc"

legacy_dropin="${DESTDIR:-}/etc/systemd/system/bascula-app.service.d/tty.conf"
if [[ -f "${legacy_dropin}" ]]; then
  rm -f "${legacy_dropin}" || true
  dropin_dir="$(dirname "${legacy_dropin}")"
  rmdir "${dropin_dir}" 2>/dev/null || true
fi

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

setup_x735_services

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

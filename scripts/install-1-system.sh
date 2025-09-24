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
lines = [line.rstrip("\n") for line in content.splitlines() if line.strip()]

def upsert_setting(prefix, target):
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith(prefix):
            lines[idx] = target
            break
    else:
        lines.append(target)

upsert_setting("enable_uart=", "enable_uart=1")
upsert_setting("dtparam=i2c_arm", "dtparam=i2c_arm=on")

LEGACY = {
    "dtoverlay=pi3-miniuart-bt",
    "dtoverlay=miniuart-bt",
    "dtoverlay=disable-bt",
}
lines = [line for line in lines if line.strip() not in LEGACY]

cfg_path.write_text("\n".join(lines) + ("\n" if lines else ""))
PYTHON

  if ! grep -qE '^dtparam=i2c_arm=on$' "${cfg}"; then
    printf 'dtparam=i2c_arm=on\n' >>"${cfg}"
  fi

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
  alsa-utils sox espeak-ng libasound2-dev piper

configure_boot_firmware "${DESTDIR:-}"

for svc in hciuart.service serial-getty@serial0.service serial-getty@ttyAMA0.service; do
  run_systemctl disable "${svc}" 2>/dev/null || true
  run_systemctl stop "${svc}" 2>/dev/null || true
done

getent group render >/dev/null || groupadd render
usermod -aG dialout,tty,video,render,input "${TARGET_USER}" || true

install -d -m 0755 "${STATE_DIR}"
echo ok > "${MARKER}"
echo "[INFO] Parte 1 completada. Reinicia ahora."

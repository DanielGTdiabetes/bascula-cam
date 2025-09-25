#!/usr/bin/env bash
set -euo pipefail

log() {
  printf '[smoke] %s\n' "$*"
}

fail() {
  printf '[smoke][ERROR] %s\n' "$*" >&2
  exit 1
}

warn() {
  printf '[smoke][WARN] %s\n' "$*" >&2
}

run_systemd_verify() {
  if command -v systemd-analyze >/dev/null 2>&1; then
    log 'Verificando unidades systemd con systemd-analyze'
    systemd-analyze verify /etc/systemd/system/*.service
  else
    warn 'systemd-analyze no disponible, omitiendo verificación de unidades'
  fi
}

check_xorg_wrap() {
  local target="/usr/lib/xorg/Xorg.wrap"
  if [[ ! -f "${target}" ]]; then
    fail "No existe ${target}"
  fi
  local mode
  mode=$(stat -c %A "${target}")
  if [[ "${mode}" != "-rwsr-sr-x" ]]; then
    fail "Permisos inesperados en ${target}: ${mode}"
  fi
  log "Permisos de Xorg.wrap verificados (${mode})"
}

check_xwrapper_config() {
  local config="/etc/X11/Xwrapper.config"
  if [[ ! -f "${config}" ]]; then
    fail "No existe ${config}"
  fi
  grep -qx 'allowed_users=anybody' "${config}" || fail "allowed_users=anybody ausente en ${config}"
  grep -qx 'needs_root_rights=yes' "${config}" || fail "needs_root_rights=yes ausente en ${config}"
  log 'Xwrapper.config válido'
}

detect_kms_card() {
  local status_file card=""
  for status_file in /sys/class/drm/card*-HDMI-A-*/status; do
    [[ -f "${status_file}" ]] || continue
    if [[ "$(<"${status_file}")" == "connected" ]]; then
      card="${status_file%/HDMI-A-*}"
      card="${card##*/}"
      break
    fi
  done
  if [[ -z "${card}" ]]; then
    if [[ -e /sys/class/drm/card1 ]]; then
      card='card1'
    elif [[ -e /sys/class/drm/card0 ]]; then
      card='card0'
    else
      fail 'No se encontraron dispositivos DRM en /sys/class/drm'
    fi
  fi
  printf '%s' "${card}"
}

check_kmsdev() {
  local conf="/etc/X11/xorg.conf.d/20-modesetting.conf"
  if [[ ! -f "${conf}" ]]; then
    fail "No existe ${conf}"
  fi
  local expected_card
  expected_card="$(detect_kms_card)"
  local expected="/dev/dri/${expected_card}"
  local configured
  configured=$(awk 'tolower($0) ~ /option[[:space:]]+"kmsdev"/ {
    if (match($0, "/dev/dri/[a-z0-9]+")) {
      print substr($0, RSTART, RLENGTH)
      exit
    }
  }' "${conf}")
  if [[ -z "${configured}" ]]; then
    fail "No se encontró Option \"kmsdev\" en ${conf}"
  fi
  if [[ "${configured}" != "${expected}" ]]; then
    fail "kmsdev configurado (${configured}) no coincide con HDMI activo (${expected})"
  fi
  log "kmsdev configurado correctamente (${configured})"
}

run_systemd_verify
check_xorg_wrap
check_xwrapper_config
check_kmsdev

log 'Smoke tests completados'

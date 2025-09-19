#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_USER="${TARGET_USER:-pi}"
USER_HOME="$(eval echo "~${TARGET_USER}" 2>/dev/null || true)"
APP_DIR_OVERRIDE="${APP_DIR:-}"
APP_DIR="${APP_DIR_OVERRIDE:-}"
APP_DIR_DEFAULT=""
VENV_DIR=""
PIP_CACHE=""
UDEV_RULE="/etc/udev/rules.d/90-bascula.rules"

log() { printf '[inst] %s\n' "$*"; }
ok() { printf '[ok] %s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*"; }
err() { printf '[err] %s\n' "$*" >&2; }

ensure_user_exists() {
  if ! id -u "${TARGET_USER}" >/dev/null 2>&1; then
    err "El usuario ${TARGET_USER} no existe"
    exit 1
  fi
}

resolve_user_home() {
  if [[ -z "${USER_HOME}" || "${USER_HOME}" == "~${TARGET_USER}" ]]; then
    USER_HOME="$(getent passwd "${TARGET_USER}" | cut -d: -f6)"
  fi
  if [[ -z "${USER_HOME}" ]]; then
    err "No se pudo determinar HOME de ${TARGET_USER}"
    exit 1
  fi
}

run_as_target() {
  if command -v sudo >/dev/null 2>&1; then
    sudo -u "${TARGET_USER}" -H "$@"
  else
    local cmd
    cmd="$(printf '%q ' "$@")"
    cmd="${cmd% }"
    su - "${TARGET_USER}" -c "${cmd}"
  fi
}

ensure_app_dir() {
  if [[ ! -d "${APP_DIR}" ]]; then
    err "Repositorio no encontrado en ${APP_DIR}. Establézcalo con APP_DIR o clone en ${APP_DIR_DEFAULT}"
    exit 1
  fi
}

prepare_cache() {
  install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_USER}" "${USER_HOME}"
  install -d -m 0700 -o "${TARGET_USER}" -g "${TARGET_USER}" "${USER_HOME}/.cache"
  install -d -m 0700 -o "${TARGET_USER}" -g "${TARGET_USER}" "${PIP_CACHE}"
}

make_scripts_executable() {
  if [[ -d "${APP_DIR}/scripts" ]]; then
    while IFS= read -r file; do
      chmod 0755 "${file}"
    done < <(find "${APP_DIR}/scripts" -maxdepth 1 -type f -name '*.sh')
  fi
}

setup_virtualenv() {
  if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    log "Creando entorno virtual en ${VENV_DIR}"
    run_as_target python3 -m venv "${VENV_DIR}"
    ok "Entorno virtual creado"
  else
    log "Entorno virtual existente reutilizado"
  fi
  run_as_target env PIP_CACHE_DIR="${PIP_CACHE}" "${VENV_DIR}/bin/python" -m pip install --upgrade pip setuptools wheel
  if [[ -f "${APP_DIR}/requirements.txt" ]]; then
    run_as_target env PIP_CACHE_DIR="${PIP_CACHE}" "${VENV_DIR}/bin/python" -m pip install -r "${APP_DIR}/requirements.txt"
  else
    warn "requirements.txt no encontrado en ${APP_DIR}"
  fi
}

install_systemd_units() {
  install -d -m 0755 /etc/systemd/system

  local escaped_app_dir escaped_user_home
  escaped_app_dir=$(printf '%s' "${APP_DIR}" | sed 's/[\/&]/\\&/g')
  escaped_user_home=$(printf '%s' "${USER_HOME}" | sed 's/[\/&]/\\&/g')

  render_and_install_unit() {
    local source_file="$1"
    local target_file="$2"
    local tmp
    tmp=$(mktemp)
    sed -e "s|User=pi|User=${TARGET_USER}|g" \
      -e "s|/home/pi/bascula-cam|${escaped_app_dir}|g" \
      -e "s|/home/pi/.Xauthority|${escaped_user_home}/.Xauthority|g" \
      -e "s|/home/pi|${escaped_user_home}|g" \
      "${source_file}" >"${tmp}"
    install -m 0644 "${tmp}" "/etc/systemd/system/${target_file}"
    rm -f "${tmp}"
  }

  render_and_install_unit "${REPO_ROOT}/etc/systemd/system/bascula-ui.service" "bascula-ui.service"
  render_and_install_unit "${REPO_ROOT}/etc/systemd/system/bascula-recovery.service" "bascula-recovery.service"
  render_and_install_unit "${REPO_ROOT}/etc/systemd/system/bascula-miniweb.service" "bascula-miniweb.service"

  ok "Servicios systemd desplegados"
}

configure_serial_access() {
  if usermod -a -G dialout,tty "${TARGET_USER}"; then
    ok "${TARGET_USER} añadido a grupos dialout y tty"
  else
    warn "No se pudieron ajustar los grupos dialout/tty para ${TARGET_USER}"
  fi
  cat <<'RULE' > "${UDEV_RULE}"
SUBSYSTEM=="tty", MODE="0666"
RULE
  chmod 0644 "${UDEV_RULE}"
  if udevadm control --reload; then
    ok "Reglas udev recargadas"
  else
    warn "No se pudo recargar udev"
  fi
}

check_piper_assets() {
  local models_dir="/opt/piper/models"
  local default_voice="${models_dir}/.default-voice"
  if [[ ! -s "${default_voice}" ]]; then
    warn "Piper sin voz por defecto. Ejecuta ${APP_DIR}/scripts/install-piper-voices.sh si necesitas TTS"
  fi
}

main() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    err "Este script debe ejecutarse como root"
    exit 1
  fi

  ensure_user_exists
  resolve_user_home
  APP_DIR_DEFAULT="${USER_HOME}/bascula-cam"
  if [[ -n "${APP_DIR_OVERRIDE}" ]]; then
    APP_DIR="${APP_DIR_OVERRIDE}"
  else
    APP_DIR="${APP_DIR_DEFAULT}"
  fi
  VENV_DIR="${APP_DIR}/.venv"
  PIP_CACHE="${USER_HOME}/.cache/pip"
  ensure_app_dir
  prepare_cache
  make_scripts_executable
  setup_virtualenv
  install_systemd_units
  configure_serial_access

  systemctl daemon-reload

  pushd "${APP_DIR}" >/dev/null
  local verify_status=0
  if ./scripts/verify-all.sh; then
    verify_status=0
  else
    verify_status=$?
    warn "scripts/verify-all.sh finalizó con código ${verify_status}. Servicios no habilitados"
  fi
  popd >/dev/null

  if (( verify_status == 0 )); then
    systemctl enable --now bascula-miniweb.service bascula-ui.service
    ok "Servicios habilitados"
  else
    err "Instalación incompleta: revise los logs"
    check_piper_assets
    echo "Reinicia manualmente si usas kiosk-xorg"
    exit "${verify_status}"
  fi

  check_piper_assets
  echo "Reinicia manualmente si usas kiosk-xorg"
}

main "$@"

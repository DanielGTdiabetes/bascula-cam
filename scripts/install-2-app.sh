#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_USER="${TARGET_USER:-pi}"
PHASE_DIR="/var/lib/bascula"
RESUME_FILE="/etc/profile.d/bascula-resume.sh"

log() { printf '[inst] %s\n' "$*"; }
ok() { printf '[ok] %s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*"; }
err() { printf '[err] %s\n' "$*" >&2; }

usage() {
  cat <<'USAGE'
Uso: install-2-app.sh [--resume]

  --resume  Ejecutado automáticamente tras el reinicio de fase 1
USAGE
  exit "${1:-0}"
}

RESUME_MODE=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --resume)
      RESUME_MODE=true
      ;;
    -h|--help)
      usage 0
      ;;
    *)
      err "Opción no reconocida: $1"
      usage 1
      ;;
  esac
  shift
done

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  err "Este script debe ejecutarse como root"
  exit 1
fi

if ! id -u "${TARGET_USER}" >/dev/null 2>&1; then
  err "El usuario ${TARGET_USER} no existe"
  exit 1
fi

TARGET_HOME="$(getent passwd "${TARGET_USER}" | cut -d: -f6)"
APP_DIR="${TARGET_HOME}/bascula-cam"
VENV_DIR="${APP_DIR}/.venv"
PYTHON="python3"

if [[ ! -d "${APP_DIR}" ]]; then
  err "No se encuentra el repositorio en ${APP_DIR}"
  exit 1
fi

install -d -m 0755 "${PHASE_DIR}"

log "Preparando entorno virtual"
if [[ ! -d "${VENV_DIR}" ]]; then
  sudo -u "${TARGET_USER}" -- "${PYTHON}" -m venv "${VENV_DIR}"
  ok "Entorno virtual creado"
else
  log "Entorno virtual existente reutilizado"
fi
sudo -u "${TARGET_USER}" -- "${VENV_DIR}/bin/python" -m pip install --upgrade pip setuptools wheel
sudo -u "${TARGET_USER}" -- "${VENV_DIR}/bin/pip" install -r "${REPO_ROOT}/requirements.txt"

log "Instalando servicios systemd"
install -m 0644 "${REPO_ROOT}/etc/systemd/system/bascula-ui.service" /etc/systemd/system/bascula-ui.service
install -m 0644 "${REPO_ROOT}/etc/systemd/system/bascula-miniweb.service" /etc/systemd/system/bascula-miniweb.service

RECOVERY_UNIT="${REPO_ROOT}/etc/systemd/system/bascula-recovery.service"
RECOVERY_AVAILABLE=false
if [[ -f "${APP_DIR}/bascula/ui/recovery_ui.py" && -f "${RECOVERY_UNIT}" ]]; then
  install -m 0644 "${RECOVERY_UNIT}" /etc/systemd/system/bascula-recovery.service
  RECOVERY_AVAILABLE=true
fi

systemctl daemon-reload
systemctl enable bascula-ui.service bascula-miniweb.service

if systemctl restart bascula-miniweb.service >/dev/null 2>&1; then
  ok "bascula-miniweb reiniciado"
else
  warn "No se pudo iniciar bascula-miniweb (se activará tras reinicio)"
fi
if systemctl restart bascula-ui.service >/dev/null 2>&1; then
  ok "bascula-ui reiniciado"
else
  warn "No se pudo iniciar bascula-ui (requiere entorno gráfico)"
fi

if ${RECOVERY_AVAILABLE}; then
  systemctl enable bascula-recovery.service
  if systemctl restart bascula-recovery.service >/dev/null 2>&1; then
    ok "bascula-recovery reiniciado"
  else
    warn "No se pudo iniciar bascula-recovery (requiere entorno gráfico)"
  fi
else
  log "bascula-recovery no disponible"
fi

printf 'PHASE=2_DONE\n' > "${PHASE_DIR}/phase"

if ${RESUME_MODE} && [[ -f "${RESUME_FILE}" ]]; then
  rm -f "${RESUME_FILE}"
  ok "Script de reanudación eliminado"
fi

ok "Fase 2 completada"

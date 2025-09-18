#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_USER="${TARGET_USER:-pi}"
USER_HOME="$(eval echo "~${TARGET_USER}")"
APP_DIR="${APP_DIR:-$USER_HOME/bascula-cam}"
VENV_DIR="$APP_DIR/.venv"
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

if [[ "${USER_HOME}" == "~${TARGET_USER}" ]]; then
  USER_HOME="$(getent passwd "${TARGET_USER}" | cut -d: -f6)"
fi

if [[ -z "${USER_HOME}" ]]; then
  err "No se pudo determinar el HOME de ${TARGET_USER}"
  exit 1
fi

PYTHON="python3"

if [[ ! -d "${APP_DIR}" ]]; then
  err "No se encuentra el repositorio en ${APP_DIR}"
  exit 1
fi

install -d -m 0755 "${PHASE_DIR}"

log "Preparando entorno virtual"
if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  sudo -u "${TARGET_USER}" -H "${PYTHON}" -m venv "${VENV_DIR}"
  ok "Entorno virtual creado"
else
  log "Entorno virtual existente reutilizado"
fi

sudo -u "${TARGET_USER}" -H mkdir -p "${USER_HOME}/.cache/pip"
sudo chown -R "${TARGET_USER}:${TARGET_USER}" "${USER_HOME}/.cache"
export PIP_CACHE_DIR="${USER_HOME}/.cache/pip"

sudo -u "${TARGET_USER}" -H env PIP_CACHE_DIR="${PIP_CACHE_DIR}" "${VENV_DIR}/bin/python" -m pip install --upgrade pip wheel setuptools
if [[ -f "${APP_DIR}/requirements.txt" ]]; then
  sudo -u "${TARGET_USER}" -H env PIP_CACHE_DIR="${PIP_CACHE_DIR}" "${VENV_DIR}/bin/python" -m pip install -r "${APP_DIR}/requirements.txt"
else
  warn "requirements.txt no encontrado"
fi
# Asegurar uvicorn disponible incluso si no figura en requirements.txt
sudo -u "${TARGET_USER}" -H env PIP_CACHE_DIR="${PIP_CACHE_DIR}" "${VENV_DIR}/bin/python" - <<'PY'
import importlib.util, sys
sys.exit(0 if importlib.util.find_spec("uvicorn") else 1)
PY
if [[ $? -ne 0 ]]; then
  sudo -u "${TARGET_USER}" -H env PIP_CACHE_DIR="${PIP_CACHE_DIR}" "${VENV_DIR}/bin/python" -m pip install uvicorn
fi
sudo -u "${TARGET_USER}" -H env PIP_CACHE_DIR="${PIP_CACHE_DIR}" "${VENV_DIR}/bin/python" "${REPO_ROOT}/tools/check_symbols.py" \
  || echo "[warn] check_symbols detectó ausencias; revisar antes de reboot"

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
systemctl enable bascula-miniweb.service
systemctl enable bascula-ui.service

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

sudo chown -R "${TARGET_USER}:${TARGET_USER}" "${APP_DIR}"

printf 'PHASE=2_DONE\n' > "${PHASE_DIR}/phase"

if ${RESUME_MODE} && [[ -f "${RESUME_FILE}" ]]; then
  rm -f "${RESUME_FILE}"
  ok "Script de reanudación eliminado"
fi

ok "Fase 2 completada"

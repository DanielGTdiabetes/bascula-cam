#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_USER="${TARGET_USER:-pi}"
USER_HOME="$(eval echo "~${TARGET_USER}")"
APP_DIR="${APP_DIR:-$USER_HOME/bascula-cam}"
VENV_DIR="${APP_DIR}/.venv"
PHASE_DIR="/var/lib/bascula"
RESUME_FILE="/etc/profile.d/bascula-resume.sh"

log() { printf '[inst] %s\n' "$*"; }
ok() { printf '[ok] %s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*"; }
err() { printf '[err] %s\n' "$*" >&2; }

usage() {
  cat <<'USAGE'
Uso: install-2-app.sh [--resume]

  --resume  Ejecutado automáticamente tras reinicio
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
  err "No se pudo determinar HOME de ${TARGET_USER}"
  exit 1
fi

if [[ ! -d "${APP_DIR}" ]]; then
  err "Repositorio no encontrado en ${APP_DIR}"
  exit 1
fi

install -d -m 0755 "${PHASE_DIR}"
install -d -m 0755 -o "${TARGET_USER}" -g "${TARGET_USER}" "${USER_HOME}"
install -d -m 0700 -o "${TARGET_USER}" -g "${TARGET_USER}" "${USER_HOME}/.cache"
install -d -m 0700 -o "${TARGET_USER}" -g "${TARGET_USER}" "${USER_HOME}/.cache/pip"
export PIP_CACHE_DIR="${USER_HOME}/.cache/pip"

log "Preparando entorno virtual"
if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  sudo -u "${TARGET_USER}" -H python3 -m venv "${VENV_DIR}"
  ok "Entorno virtual creado"
else
  log "Entorno virtual existente reutilizado"
fi

sudo -u "${TARGET_USER}" -H PIP_CACHE_DIR="${PIP_CACHE_DIR}" "${VENV_DIR}/bin/python" -m pip install --upgrade pip setuptools wheel
if [[ -f "${APP_DIR}/requirements.txt" ]]; then
  sudo -u "${TARGET_USER}" -H PIP_CACHE_DIR="${PIP_CACHE_DIR}" "${VENV_DIR}/bin/python" -m pip install -r "${APP_DIR}/requirements.txt"
else
  warn "requirements.txt no encontrado"
fi

if ! sudo -u "${TARGET_USER}" -H "${VENV_DIR}/bin/python" - <<'PY'
import importlib, sys
sys.exit(0 if importlib.util.find_spec("uvicorn") else 1)
PY
then
  sudo -u "${TARGET_USER}" -H PIP_CACHE_DIR="${PIP_CACHE_DIR}" "${VENV_DIR}/bin/python" -m pip install uvicorn
fi

if ! command -v rsvg-convert >/dev/null 2>&1; then
  log "Instalando librsvg2-bin para assets de la mascota"
  apt-get update
  apt-get install -y librsvg2-bin
fi

if sudo -u "${TARGET_USER}" -H bash "${APP_DIR}/scripts/build-mascot-assets.sh"; then
  ok "PNG de la mascota generados"
else
  warn "no se pudieron generar los PNG de la mascota"
fi

sudo chown -R "${TARGET_USER}:${TARGET_USER}" "${APP_DIR}" || true
if [[ -f "${APP_DIR}/scripts/safe_run.sh" ]]; then
  chmod 0755 "${APP_DIR}/scripts/safe_run.sh" || true
fi

log "Instalando servicios systemd"
cat <<EOF_UI > /etc/systemd/system/bascula-ui.service
[Unit]
Description=Bascula UI (Tkinter Kiosk)
After=graphical.target
Wants=graphical.target

[Service]
User=${TARGET_USER}
WorkingDirectory=${APP_DIR}
Environment=DISPLAY=:0
Environment=XAUTHORITY=${USER_HOME}/.Xauthority
Environment=PYTHONUNBUFFERED=1
ExecStartPre=/bin/sh -c 'for i in $(seq 1 30); do [ -S /tmp/.X11-unix/X0 ] && exit 0; sleep 0.5; done; exit 1'
ExecStart=${APP_DIR}/scripts/safe_run.sh
Restart=on-failure
RestartSec=2

[Install]
WantedBy=graphical.target
EOF_UI
chmod 0644 /etc/systemd/system/bascula-ui.service

cat <<EOF_WEB > /etc/systemd/system/bascula-miniweb.service
[Unit]
Description=Bascula Mini Web
After=network-online.target
Wants=network-online.target

[Service]
User=${TARGET_USER}
WorkingDirectory=${APP_DIR}
ExecStartPre=/bin/sh -c '[ -x ${VENV_DIR}/bin/python ]'
ExecStartPre=/bin/sh -c '${VENV_DIR}/bin/python -c "import uvicorn"'
ExecStart=${VENV_DIR}/bin/python -m uvicorn bascula.services.miniweb:app --host 0.0.0.0 --port 8080
Restart=always

[Install]
WantedBy=multi-user.target
EOF_WEB
chmod 0644 /etc/systemd/system/bascula-miniweb.service

RECOVERY_SRC="${APP_DIR}/bascula/ui/recovery_ui.py"
if [[ -f "${RECOVERY_SRC}" ]]; then
  cat <<EOF_REC > /etc/systemd/system/bascula-recovery.service
[Unit]
Description=Bascula Recovery UI (fallback Tkinter)
After=graphical.target
Wants=graphical.target

[Service]
User=${TARGET_USER}
WorkingDirectory=${APP_DIR}
Environment=DISPLAY=:0
Environment=XAUTHORITY=${USER_HOME}/.Xauthority
Environment=PYTHONUNBUFFERED=1
ExecStartPre=/usr/bin/python3 -m py_compile ${APP_DIR}/main.py
ExecStartPre=/bin/sh -c 'for i in $(seq 1 30); do [ -S /tmp/.X11-unix/X0 ] && exit 0; sleep 0.5; done; exit 1'
ExecStart=/usr/bin/python3 ${APP_DIR}/bascula/ui/recovery_ui.py
Restart=on-failure
RestartSec=2

[Install]
WantedBy=graphical.target
EOF_REC
  chmod 0644 /etc/systemd/system/bascula-recovery.service
  systemctl enable bascula-recovery.service >/dev/null 2>&1 || true
else
  rm -f /etc/systemd/system/bascula-recovery.service
fi

systemctl daemon-reload
systemctl enable bascula-miniweb.service >/dev/null 2>&1 || true

if [[ -f "${USER_HOME}/.xinitrc" && $(grep -F "safe_run.sh" "${USER_HOME}/.xinitrc" || true) ]]; then
  systemctl disable bascula-ui.service >/dev/null 2>&1 || true
  warn "bascula-ui.service deshabilitado (arranque vía xinitrc)"
else
  systemctl enable bascula-ui.service >/dev/null 2>&1 || true
fi

if systemctl is-active bascula-miniweb.service >/dev/null 2>&1; then
  ok "bascula-miniweb activo"
else
  systemctl restart bascula-miniweb.service >/dev/null 2>&1 || warn "No se pudo iniciar bascula-miniweb"
fi

if systemctl is-enabled bascula-ui.service >/dev/null 2>&1; then
  systemctl restart bascula-ui.service >/dev/null 2>&1 || warn "No se pudo iniciar bascula-ui"
fi

printf 'PHASE=2_DONE\n' > "${PHASE_DIR}/phase"

if ${RESUME_MODE} && [[ -f "${RESUME_FILE}" ]]; then
  rm -f "${RESUME_FILE}"
  ok "Script de reanudación eliminado"
fi

ok "Fase 2 completada"

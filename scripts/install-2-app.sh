#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_USER="${TARGET_USER:-pi}"
PHASE_DIR="/var/lib/bascula"

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

log "Creando entorno virtual"
sudo -u "${TARGET_USER}" -- "${PYTHON}" -m venv "${VENV_DIR}" >/dev/null 2>&1 || \
  sudo -u "${TARGET_USER}" -- "${PYTHON}" -m venv "${VENV_DIR}"
sudo -u "${TARGET_USER}" -- "${VENV_DIR}/bin/python" -m pip install --upgrade pip setuptools wheel
sudo -u "${TARGET_USER}" -- "${VENV_DIR}/bin/pip" install -r "${REPO_ROOT}/requirements.txt"

log "Creando servicios systemd"
cat <<UI > /etc/systemd/system/bascula-ui.service
[Unit]
Description=Bascula UI (Tkinter Kiosk)
After=graphical.target
Wants=graphical.target

[Service]
User=${TARGET_USER}
WorkingDirectory=${APP_DIR}
Environment=DISPLAY=:0
Environment=XAUTHORITY=${TARGET_HOME}/.Xauthority
Environment=PYTHONUNBUFFERED=1
# Espera activa a que exista el socket de X :0 (máx ~15s)
ExecStartPre=/bin/sh -c 'for i in \$(seq 1 30); do [ -S /tmp/.X11-unix/X0 ] && exit 0; sleep 0.5; done; exit 1'
ExecStart=${APP_DIR}/scripts/safe_run.sh
Restart=on-failure
RestartSec=2

[Install]
WantedBy=graphical.target
UI

RECOVERY_UI="${APP_DIR}/bascula/ui/recovery_ui.py"
RECOVERY_AVAILABLE=false
if [[ -f "${RECOVERY_UI}" ]]; then
  cat <<REC > /etc/systemd/system/bascula-recovery.service
[Unit]
Description=Bascula Recovery UI (fallback Tkinter)
After=graphical.target
Wants=graphical.target

[Service]
User=${TARGET_USER}
WorkingDirectory=${APP_DIR}
Environment=DISPLAY=:0
Environment=XAUTHORITY=${TARGET_HOME}/.Xauthority
Environment=PYTHONUNBUFFERED=1
ExecStartPre=/usr/bin/python3 -m py_compile ${APP_DIR}/main.py
ExecStartPre=/bin/sh -c 'for i in \$(seq 1 30); do [ -S /tmp/.X11-unix/X0 ] && exit 0; sleep 0.5; done; exit 1'
ExecStart=/usr/bin/python3 ${APP_DIR}/bascula/ui/recovery_ui.py
Restart=on-failure
RestartSec=2

[Install]
WantedBy=graphical.target
REC
  RECOVERY_AVAILABLE=true
fi

cat <<WEB > /etc/systemd/system/bascula-miniweb.service
[Unit]
Description=Bascula Mini Web
After=network-online.target

[Service]
User=${TARGET_USER}
WorkingDirectory=${APP_DIR}
ExecStart=${APP_DIR}/.venv/bin/uvicorn bascula.services.miniweb:app --host 0.0.0.0 --port 8080
Restart=always

[Install]
WantedBy=multi-user.target
WEB

systemctl daemon-reload
if systemctl enable bascula-ui.service; then
  ok "Servicio bascula-ui habilitado"
else
  warn "No se pudo habilitar bascula-ui"
fi

if [[ ${RECOVERY_AVAILABLE} == true ]]; then
  if systemctl enable bascula-recovery.service; then
    ok "Servicio bascula-recovery habilitado"
  else
    warn "No se pudo habilitar bascula-recovery"
  fi
else
  log "bascula-recovery no disponible (archivo ${RECOVERY_UI} no encontrado)"
fi

if systemctl enable bascula-miniweb.service; then
  ok "Servicio bascula-miniweb habilitado"
else
  warn "No se pudo habilitar bascula-miniweb"
fi
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

if [[ ${RECOVERY_AVAILABLE} == true ]]; then
  if systemctl restart bascula-recovery.service >/dev/null 2>&1; then
    ok "bascula-recovery reiniciado"
  else
    warn "No se pudo iniciar bascula-recovery (requiere entorno gráfico)"
  fi
fi

install -d -m 0755 "${PHASE_DIR}"
printf 'PHASE=2_DONE\n' > "${PHASE_DIR}/phase"

if ${RESUME_MODE}; then
  rm -f /etc/profile.d/bascula-resume.sh
fi

ok "Fase 2 completada"

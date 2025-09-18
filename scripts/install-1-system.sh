#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PHASE_DIR="/var/lib/bascula"
TARGET_USER="${TARGET_USER:-pi}"

log() { printf '[inst] %s\n' "$*"; }
ok() { printf '[ok] %s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*"; }
err() { printf '[err] %s\n' "$*" >&2; }

usage() {
  cat <<'USAGE'
Uso: install-1-system.sh [--from-all] [--skip-reboot]

  --from-all     Invocado por install-all.sh (crea reanudación automática)
  --skip-reboot  No ejecutar reboot al finalizar (para depuración manual)
USAGE
  exit "${1:-0}"
}

FROM_ALL=false
SKIP_REBOOT=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --from-all)
      FROM_ALL=true
      ;;
    --skip-reboot)
      SKIP_REBOOT=true
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

log "Añadiendo ${TARGET_USER} a grupos de dispositivos"
usermod -aG dialout,tty,gpio,i2c,spi "${TARGET_USER}" || true

log "Instalando paquetes base"
export DEBIAN_FRONTEND=noninteractive
apt-get update
BASE_PACKAGES=(
  git curl rsync unzip jq
  xserver-xorg xinit x11-xserver-utils
  matchbox-window-manager
  python3-tk
  libcamera-apps python3-picamera2
  alsa-utils sox
  piper
  i2c-tools
)
apt-get install -y "${BASE_PACKAGES[@]}"

log "Configurando permisos de dispositivos de báscula"
RULES_FILE="/etc/udev/rules.d/99-scale.rules"
if [[ ! -f "${RULES_FILE}" ]]; then
  cat <<'RULES' > "${RULES_FILE}"
# Báscula Cam – permisos para interfaces serie de la báscula
SUBSYSTEM=="tty", KERNEL=="ttyACM[0-9]*", MODE="0660", GROUP="dialout", SYMLINK+="bascula"
SUBSYSTEM=="tty", KERNEL=="ttyUSB[0-9]*", MODE="0660", GROUP="dialout", SYMLINK+="bascula"
RULES
  chmod 0644 "${RULES_FILE}"
else
  grep -q 'ttyACM' "${RULES_FILE}" || echo 'SUBSYSTEM=="tty", KERNEL=="ttyACM[0-9]*", MODE="0660", GROUP="dialout", SYMLINK+="bascula"' >> "${RULES_FILE}"
  grep -q 'ttyUSB' "${RULES_FILE}" || echo 'SUBSYSTEM=="tty", KERNEL=="ttyUSB[0-9]*", MODE="0660", GROUP="dialout", SYMLINK+="bascula"' >> "${RULES_FILE}"
fi
udevadm control --reload-rules && udevadm trigger || true

log "Creando entorno /etc/bascula/bascula.env"
install -d -m 0755 /etc/bascula
ENV_FILE="/etc/bascula/bascula.env"
if [[ ! -f "${ENV_FILE}" ]]; then
  cat <<'ENV' > "${ENV_FILE}"
# BASCULA_DEVICE=/dev/bascula
# BASCULA_FILTER_WINDOW=5
# BASCULA_SAMPLE_MS=100
ENV
  chmod 0644 "${ENV_FILE}"
fi

log "Configurando modo kiosko (autologin + startx)"
"${SCRIPT_DIR}/install-kiosk-xorg.sh" "${TARGET_USER}" "${TARGET_HOME}"

log "Instalando voces Piper"
if bash "${SCRIPT_DIR}/install-piper-voices.sh"; then
  ok "Voces Piper instaladas"
else
  warn "Voces Piper no instaladas (continuo sin abortar Fase 1)"
fi

log "Configurando soporte X735"
X735_SRC="${REPO_ROOT}/scripts/x735.sh"
X735_INSTALLED=false
if [[ -f "${X735_SRC}" ]]; then
  install -m 0755 "${X735_SRC}" /usr/local/bin/x735.sh
  X735_INSTALLED=true
  ok "x735.sh desplegado en /usr/local/bin"
  if ! command -v dos2unix >/dev/null 2>&1; then
    apt-get install -y dos2unix
  fi
  dos2unix /usr/local/bin/x735.sh >/dev/null 2>&1 || true
else
  warn "scripts/x735.sh no encontrado; se omite despliegue"
fi

X735_POWEROFF_SRC="${REPO_ROOT}/scripts/x735-poweroff.sh"
if [[ -f "${X735_POWEROFF_SRC}" ]]; then
  install -m 0755 "${X735_POWEROFF_SRC}" /lib/systemd/system-shutdown/x735-poweroff.sh
  ok "x735-poweroff.sh instalado en system-shutdown"
else
  warn "scripts/x735-poweroff.sh no encontrado; se omite despliegue"
fi

if ${X735_INSTALLED}; then
  X735_UNIT_DST="/etc/systemd/system/x735-fan.service"
  X735_UNIT_SRC="${REPO_ROOT}/etc/systemd/system/x735-fan.service"
  if [[ -f "${X735_UNIT_SRC}" ]]; then
    install -m 0644 "${X735_UNIT_SRC}" "${X735_UNIT_DST}"
  else
    cat <<'UNIT' > "${X735_UNIT_DST}"
[Unit]
Description=X735 v3 Fan and Power Management
After=multi-user.target

[Service]
ExecStart=/usr/local/bin/x735.sh
Restart=always
User=root

[Install]
WantedBy=multi-user.target
UNIT
    chmod 0644 "${X735_UNIT_DST}"
  fi
  if systemctl daemon-reload && systemctl enable x735-fan.service && systemctl restart x735-fan.service; then
    ok "Servicio x735-fan habilitado y reiniciado"
  else
    echo "[warn] x735-fan no arrancó, revisar hardware/logs"
  fi
else
  warn "No se instala servicio x735-fan: falta scripts/x735.sh"
fi

log "Verificaciones ligeras"
if command -v Xorg >/dev/null 2>&1; then
  Xorg -version 2>&1 | head -n1 | sed 's/^/[ok] Xorg /'
else
  warn "Xorg no disponible"
fi
if command -v xinit >/dev/null 2>&1; then
  xinit --version 2>&1 | head -n1 | sed 's/^/[ok] xinit /'
else
  warn "xinit no disponible"
fi
if command -v libcamera-hello >/dev/null 2>&1; then
  if libcamera-hello --version >/dev/null 2>&1; then
    libcamera-hello --version 2>&1 | head -n1 | sed 's/^/[ok] libcamera /'
  else
    warn "libcamera-hello devuelve error (¿sin cámara?)"
  fi
else
  warn "libcamera-hello no encontrado"
fi
if command -v aplay >/dev/null 2>&1; then
  if aplay -l >/dev/null 2>&1; then
    aplay -l 2>/dev/null | head -n3 | sed 's/^/[ok] aplay /'
  else
    warn "aplay no detecta tarjetas de sonido"
  fi
else
  warn "aplay no disponible"
fi
if command -v piper >/dev/null 2>&1; then
  ok "Binario piper disponible"
else
  warn "piper no encontrado en PATH"
fi

install -d -m 0755 "${PHASE_DIR}"
printf 'PHASE=1_DONE\n' > "${PHASE_DIR}/phase"

if ${FROM_ALL}; then
  RESUME_SCRIPT="/etc/profile.d/bascula-resume.sh"
  cat <<'RESUME' > "${RESUME_SCRIPT}"
if [ -f /var/lib/bascula/phase ] && grep -q 'PHASE=1_DONE' /var/lib/bascula/phase; then
  if command -v sudo >/dev/null 2>&1; then
    sudo /home/pi/bascula-cam/scripts/install-2-app.sh --resume
  else
    /home/pi/bascula-cam/scripts/install-2-app.sh --resume
  fi
fi
RESUME
  chmod 0644 "${RESUME_SCRIPT}"
  ok "Reanudación automática configurada"
fi

log "Fase 1 completada"
if ${SKIP_REBOOT}; then
  warn "Reinicio omitido (--skip-reboot)"
else
  log "Reiniciando el sistema"
  systemctl reboot
fi

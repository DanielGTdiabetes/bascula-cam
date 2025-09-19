#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_USER="${TARGET_USER:-pi}"
USER_HOME="$(eval echo "~${TARGET_USER}")"
APP_DIR="${APP_DIR:-$USER_HOME/bascula-cam}"
PHASE_DIR="/var/lib/bascula"
RESUME_SCRIPT="/etc/profile.d/bascula-resume.sh"
UDEV_RULE="/etc/udev/rules.d/99-scale.rules"
VOICE_SCRIPT="${SCRIPT_DIR}/install-piper-voices.sh"
KIOSK_SCRIPT="${SCRIPT_DIR}/install-kiosk-xorg.sh"

log() { printf '[inst] %s\n' "$*"; }
ok() { printf '[ok] %s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*"; }
err() { printf '[err] %s\n' "$*" >&2; }

usage() {
  cat <<'USAGE'
Uso: install-1-system.sh [--from-all] [--skip-reboot]

  --from-all     Invocado por install-all.sh (activa reanudación y reboot)
  --skip-reboot  No reiniciar al finalizar
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

if [[ "${USER_HOME}" == "~${TARGET_USER}" ]]; then
  USER_HOME="$(getent passwd "${TARGET_USER}" | cut -d: -f6)"
fi
if [[ -z "${USER_HOME}" ]]; then
  err "No se pudo determinar HOME para ${TARGET_USER}"
  exit 1
fi

log "Instalando paquetes base"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y \
  git curl rsync unzip jq \
  xserver-xorg xinit x11-xserver-utils matchbox-window-manager \
  python3-tk libcamera-apps python3-picamera2 \
  fonts-dejavu fonts-liberation fonts-noto-color-emoji \
  alsa-utils sox piper i2c-tools dos2unix librsvg2-bin

log "Configurando modo kiosko (autologin + startx)"
"${KIOSK_SCRIPT}" "${TARGET_USER}" "${USER_HOME}"

log "Desplegando scripts X735"
if [[ -f "${REPO_ROOT}/scripts/x735.sh" ]]; then
  install -m 0755 "${REPO_ROOT}/scripts/x735.sh" /usr/local/bin/x735.sh
  dos2unix /usr/local/bin/x735.sh >/dev/null 2>&1 || true
  ok "x735.sh instalado en /usr/local/bin"
else
  warn "scripts/x735.sh no encontrado"
fi
if [[ -f "${REPO_ROOT}/scripts/x735-poweroff.sh" ]]; then
  install -m 0755 "${REPO_ROOT}/scripts/x735-poweroff.sh" /lib/systemd/system-shutdown/x735-poweroff.sh
  dos2unix /lib/systemd/system-shutdown/x735-poweroff.sh >/dev/null 2>&1 || true
  ok "x735-poweroff.sh desplegado"
fi

log "Configurando servicio x735-fan"
cat <<'UNIT' > /etc/systemd/system/x735-fan.service
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
chmod 0644 /etc/systemd/system/x735-fan.service
if systemctl daemon-reload && systemctl enable x735-fan && systemctl restart x735-fan; then
  ok "x735-fan habilitado"
else
  echo "[warn] x735-fan no arrancó"
fi

log "Instalando voces Piper"
if bash "${VOICE_SCRIPT}"; then
  ok "Voces Piper instaladas"
else
  warn "Fallo instalando voces Piper"
fi

log "Ajustando grupos de pesaje"
if usermod -aG dialout,tty,gpio,i2c,spi "${TARGET_USER}"; then
  ok "${TARGET_USER} añadido a dialout,tty,gpio,i2c,spi"
else
  warn "No se pudieron ajustar los grupos para ${TARGET_USER}"
fi

cat <<'RULE' > "${UDEV_RULE}"
KERNEL=="ttyACM*", MODE="0660", GROUP="dialout"
KERNEL=="ttyUSB*", MODE="0660", GROUP="dialout"
RULE
chmod 0644 "${UDEV_RULE}"
udevadm control --reload-rules && udevadm trigger || true

install -d -m 0755 /etc/bascula
if [[ ! -f /etc/bascula/bascula.env ]]; then
  cat <<'ENV' > /etc/bascula/bascula.env
# BASCULA_DEVICE=/dev/ttyACM0
# BASCULA_FILTER_WINDOW=5
# BASCULA_SAMPLE_MS=100
ENV
  chmod 0644 /etc/bascula/bascula.env
fi

install -d -m 0755 "${PHASE_DIR}"
printf 'PHASE=1_DONE\n' > "${PHASE_DIR}/phase"

if ${FROM_ALL}; then
  cat <<EOF_RESUME > "${RESUME_SCRIPT}"
#!/usr/bin/env bash
if [ -f "${PHASE_DIR}/phase" ] && grep -q 'PHASE=1_DONE' "${PHASE_DIR}/phase"; then
  if [ -x "${APP_DIR}/scripts/install-2-app.sh" ]; then
    sudo TARGET_USER="${TARGET_USER}" APP_DIR="${APP_DIR}" bash "${APP_DIR}/scripts/install-2-app.sh" --resume
  fi
fi
EOF_RESUME
  chmod 0755 "${RESUME_SCRIPT}"
  ok "Reanudación tras reinicio preparada"
fi

log "Fase 1 completada"
if ${FROM_ALL} && ! ${SKIP_REBOOT}; then
  log "Reiniciando sistema"
  systemctl reboot
elif ${SKIP_REBOOT}; then
  warn "Reinicio omitido (--skip-reboot)"
fi

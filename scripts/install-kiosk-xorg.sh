#!/usr/bin/env bash
set -euo pipefail

TARGET_USER="${1:-pi}"
TARGET_HOME="${2:-/home/${TARGET_USER}}"
APP_DIR="${TARGET_HOME}/bascula-cam"

log() { printf '[inst] %s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*"; }

if [[ ! -d "${TARGET_HOME}" ]]; then
  warn "Directorio home ${TARGET_HOME} inexistente"
  exit 0
fi

install -d -m 0755 "${TARGET_HOME}" || true

GETTY_DIR="/etc/systemd/system/getty@tty1.service.d"
install -d -m 0755 "${GETTY_DIR}"
cat <<EOF_OVR > "${GETTY_DIR}/override.conf"
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin ${TARGET_USER} --noclear %I \$TERM
EOF_OVR
chmod 0644 "${GETTY_DIR}/override.conf"

BASH_PROFILE="${TARGET_HOME}/.bash_profile"
cat <<'EOF_PROFILE' > "${BASH_PROFILE}"
#!/usr/bin/env bash
PHASE_FILE="/var/lib/bascula/phase"

if [[ -z "${DISPLAY:-}" && $(tty) == /dev/tty1 ]]; then
  if [[ -f "${PHASE_FILE}" ]] && grep -q 'PHASE=2_DONE' "${PHASE_FILE}"; then
    exec startx -- -nocursor
  else
    echo "[bascula] Inicio gráfico pospuesto: ejecuta install-2-app.sh" >&2
  fi
fi
EOF_PROFILE
chown "${TARGET_USER}:${TARGET_USER}" "${BASH_PROFILE}" || true
chmod 0755 "${BASH_PROFILE}"

XINITRC="${TARGET_HOME}/.xinitrc"
cat <<'EOF_XINIT' > "${XINITRC}"
#!/usr/bin/env bash
set -euo pipefail

export DISPLAY=:0
export XAUTHORITY="${HOME}/.Xauthority"

if command -v xset >/dev/null 2>&1; then
  xset s off -dpms || true
  xset s noblank || true
fi

PHASE_FILE="/var/lib/bascula/phase"
if [[ ! -f "${PHASE_FILE}" ]] || ! grep -q 'PHASE=2_DONE' "${PHASE_FILE}"; then
  echo "[bascula] Instalación incompleta: ejecuta install-2-app.sh" >&2
  sleep 5
  exit 0
fi

APP_DIR="${HOME}/bascula-cam"
if command -v matchbox-window-manager >/dev/null 2>&1; then
  matchbox-window-manager -use_titlebar no -use_system_theme &
fi

if [[ -x "${APP_DIR}/scripts/safe_run.sh" ]]; then
  exec "${APP_DIR}/scripts/safe_run.sh"
else
  exec python3 "${APP_DIR}/main.py"
fi
EOF_XINIT
chown "${TARGET_USER}:${TARGET_USER}" "${XINITRC}" || true
chmod 0755 "${XINITRC}"

XAUTH_FILE="${TARGET_HOME}/.Xauthority"
if [[ -f "${XAUTH_FILE}" ]]; then
  chown "${TARGET_USER}:${TARGET_USER}" "${XAUTH_FILE}" || true
  chmod 0600 "${XAUTH_FILE}" || true
else
  install -m 0600 -o "${TARGET_USER}" -g "${TARGET_USER}" /dev/null "${XAUTH_FILE}" || true
fi

log "Autologin y startx configurados para ${TARGET_USER}"

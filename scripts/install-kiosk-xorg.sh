#!/usr/bin/env bash
set -euo pipefail

TARGET_USER="${1:-pi}"
TARGET_HOME="${2:-/home/pi}"
APP_DIR="${TARGET_HOME}/bascula-cam"

log() { printf '[inst] %s\n' "$*"; }
warn() { printf '[warn] %s\n' "$*"; }

if [[ ! -d "${TARGET_HOME}" ]]; then
  warn "Directorio home ${TARGET_HOME} inexistente"
  exit 0
fi

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
if [[ -z "${DISPLAY:-}" && $(tty) == /dev/tty1 ]]; then
  exec startx -- -nocursor
fi
EOF_PROFILE
chown "${TARGET_USER}:${TARGET_USER}" "${BASH_PROFILE}" || true
chmod 0644 "${BASH_PROFILE}"

XINITRC="${TARGET_HOME}/.xinitrc"
cat <<EOF_XINIT > "${XINITRC}"
#!/usr/bin/env bash
set -euo pipefail

xset s off -dpms
matchbox-window-manager &

exec ${APP_DIR}/scripts/safe_run.sh
EOF_XINIT
chown "${TARGET_USER}:${TARGET_USER}" "${XINITRC}" || true
chmod 0755 "${XINITRC}"

log "Autologin y startx configurados para ${TARGET_USER}"

#!/usr/bin/env bash
set -euo pipefail

export HOME="/home/pi"
export USER="pi"
export XDG_RUNTIME_DIR="/run/user/1000"
export DISPLAY=":0"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="/var/log/bascula"
LOG_FILE="${LOG_DIR}/app.log"
XORG_LOG_FILE="${LOG_DIR}/xorg.log"

log_journal() {
  if command -v logger >/dev/null 2>&1; then
    logger -t bascula-run_ui -- "$@"
  fi
}

log_info() {
  local message="[run-ui][INFO] $*"
  printf '%s\n' "${message}"
  log_journal "${message}"
}

log_error() {
  local message="[run-ui][ERROR] $*"
  printf '%s\n' "${message}" >&2
  log_journal "${message}"
}

if [[ ${EUID} -eq 0 ]]; then
  log_error "No debe ejecutarse como root"
  exit 1
fi

exec >>"${LOG_FILE}" 2>&1

start_stamp="$(date --iso-8601=seconds 2>/dev/null || date)"
log_info "Iniciando UI (${start_stamp})"

cd "${APP_DIR}"

log_info "XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR}"

if [[ ! -d .venv ]]; then
  python3 -m venv --system-site-packages .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

python - <<'PY'
try:
    import serial  # noqa: F401
except Exception:
    import sys
    import subprocess
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pyserial'])
    except Exception:
        pass
PY

deactivate || true

XINITRC="${HOME}/.xinitrc"
cat <<'SH' > "${XINITRC}"
#!/usr/bin/env bash
set -euo pipefail
exec /opt/bascula/current/scripts/xsession.sh
SH
chmod 0755 "${XINITRC}"

# Forzar Xorg sin -logfile
printf '%s\n' 'exec /usr/lib/xorg/Xorg :0 vt1 -nolisten tcp -noreset' > "${HOME}/.xserverrc"
chmod 0755 "${HOME}/.xserverrc"

exec xinit "${XINITRC}" -- /usr/bin/Xorg :0 vt1 -nolisten tcp -noreset

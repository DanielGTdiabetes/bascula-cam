#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="/var/log/bascula"
LOG_FILE="${LOG_DIR}/app.log"

if [[ ${EUID} -eq 0 ]]; then
  echo "[run-ui] No debe ejecutarse como root" >&2
  exit 1
fi

mkdir -p "${LOG_DIR}" 2>/dev/null || true
touch "${LOG_FILE}" 2>/dev/null || true
exec >>"${LOG_FILE}" 2>&1

printf '[run-ui] Iniciando UI (%s)\n' "$(date --iso-8601=seconds 2>/dev/null || date)"

cd "${APP_DIR}"

export DISPLAY=:0

uid="$(id -u)"
if [ -z "${XDG_RUNTIME_DIR:-}" ] || [ ! -w "${XDG_RUNTIME_DIR:-/dev/null}" ]; then
  if [ -d "/run/bascula-xdg" ] && [ -w "/run/bascula-xdg" ]; then
    export XDG_RUNTIME_DIR="/run/bascula-xdg"
  else
    fallback="/tmp/bascula-xdg-${uid}"
    mkdir -p -m 0700 "$fallback" 2>/dev/null || true
    export XDG_RUNTIME_DIR="$fallback"
  fi
  echo "[run-ui] XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR} (fallback)" >&2
fi

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

exec xinit "${XINITRC}" -- /usr/bin/Xorg :0 vt1 -nolisten tcp -noreset

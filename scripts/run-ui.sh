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
if touch "${LOG_FILE}" 2>/dev/null; then
  exec >>"${LOG_FILE}" 2>&1
fi

printf '[run-ui] Iniciando UI (%s)\n' "$(date --iso-8601=seconds 2>/dev/null || date)"

cd "${APP_DIR}"

export DISPLAY=:0

uid="$(id -u)"
XDG_DIR="/run/user/${uid}"
export XDG_RUNTIME_DIR="${XDG_DIR}"
if [[ ! -d "${XDG_DIR}" ]]; then
  if ! install -d -m 0700 "${XDG_DIR}"; then
    echo "[run-ui] No se pudo preparar ${XDG_DIR}" >&2
    exit 1
  fi
fi

if [[ $(stat -c %U "${XDG_DIR}" 2>/dev/null || echo "") != "$(id -un)" ]]; then
  echo "[run-ui] Advertencia: ${XDG_DIR} pertenece a otro usuario" >&2
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

exec xinit "${XINITRC}" -- /usr/bin/Xorg :0 vt1 -nolisten tcp -noreset -logfile \
  "/home/pi/.local/share/xorg/Xorg.0.log"

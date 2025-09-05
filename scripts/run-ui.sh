#!/usr/bin/env bash
set -euo pipefail

# scripts/run-ui.sh
# Lanza la UI Tk de la báscula desde la raíz del repo.
# Crea y usa un venv local (.venv) con system-site-packages.

cd "$(dirname "$0")/.."

export PYTHONUNBUFFERED=1

if [[ ! -d .venv ]]; then
  python3 -m venv --system-site-packages .venv
fi
source .venv/bin/activate

# Dependencia recomendada (silenciosa si ya está):
# Audio: detectar dispositivo si no viene definido
if command -v aplay >/dev/null 2>&1; then
  if [ -z "${BASCULA_APLAY_DEVICE:-}" ]; then
    if aplay -l 2>/dev/null | grep -qi 'hifiberry'; then
      export BASCULA_APLAY_DEVICE=plughw:0,0
    fi
  fi
fi

python - <<'PY'
try:
    import serial  # noqa: F401
except Exception:
    import sys, subprocess
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pyserial'])
    except Exception:
        # Si no hay red o pip falla, continuamos; la UI aún puede mostrarse
        pass
PY

exec python3 main.py

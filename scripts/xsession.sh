#!/usr/bin/env bash
set -euo pipefail
export DISPLAY=:0

# Anti-suspensión / cursor
xset s off || true
xset -dpms || true
xset s noblank || true
command -v unclutter >/dev/null 2>&1 && unclutter -idle 0 -root &

cd /opt/bascula/current
if [[ -f ".venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

exec python3 -m bascula.ui.app

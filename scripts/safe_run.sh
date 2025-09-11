sudo install -d -m 755 /opt/bascula/current/scripts

sudo tee /opt/bascula/current/scripts/safe_run.sh >/dev/null <<'SH'
#!/usr/bin/env bash
set -euo pipefail

# Permitir override por variable de entorno
APP_DIR="${APP_DIR:-/opt/bascula/current}"
PY="$APP_DIR/.venv/bin/python3"
RECOVERY_FLAG="/var/lib/bascula-updater/force_recovery"
ALIVE="/run/bascula.alive"

export PYTHONUNBUFFERED=1
cd "$APP_DIR"
export PYTHONPATH="$APP_DIR:${PYTHONPATH:-}"

# Si el venv no existe, usa python3 del sistema
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3)"
fi

smoke_test() { [[ -r "$APP_DIR/main.py" ]]; }
run_recovery() { exec "$PY" -m bascula.ui.recovery_ui; }

# Recovery forzado o sin main.py
if [[ -f "$RECOVERY_FLAG" ]] || ! smoke_test; then
  run_recovery
fi

# Si hay latido muy viejo, ir a recovery
if [[ -f "$ALIVE" ]]; then
  now=$(date +%s); last=$(stat -c %Y "$ALIVE" 2>/dev/null || echo 0)
  (( now - last > 15 )) && run_recovery
fi

# Lanza la app principal
exec "$PY" "$APP_DIR/main.py"
SH

sudo chown pi:pi /opt/bascula/current/scripts/safe_run.sh
sudo chmod +x /opt/bascula/current/scripts/safe_run.sh

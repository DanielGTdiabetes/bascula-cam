#!/usr/bin/env bash
# install-all.sh — Instalador robusto para Báscula Digital Pro
# - Dinámico respecto al usuario: usa $TARGET_USER y $TARGET_HOME (incluido systemd)
# - Espera educadamente si APT/DPKG están ocupados (locks)
# - Instala dependencias (incluye python3-tk)
# - Prepara /opt/bascula/releases y symlink /opt/bascula/current
# - Crea venv y instala requirements
# - Asegura ~/.bascula/{data,logs} y config.json
# - Corrige scripts/safe_run.sh (cd + PYTHONPATH)
# - Crea ~/.xinitrc y servicio systemd
#
# Uso:
#   sudo ./scripts/install-all.sh
set -Eeuo pipefail

on_err() {
  echo "Error en línea $1 (código ${2:-1}). Abortando." >&2
}
trap 'on_err ${LINENO} $?' ERR

apt_wait() {
  echo "==> Comprobando si APT/DPKG están ocupados..."
  # Espera pasiva hasta 3 minutos a que terminen apt/dpkg automáticos
  local tries=60
  while (( tries > 0 )); do
    if sudo fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 || \
       sudo fuser /var/lib/apt/lists/lock >/dev/null 2>&1 || \
       pgrep -x apt >/dev/null || pgrep -x apt-get >/dev/null || pgrep -x dpkg >/dev/null; then
      echo "   APT/DPKG ocupados; esperando 3s... (quedan $tries)"
      sleep 3
      ((tries--))
    else
      break
    fi
  done
  if (( tries == 0 )); then
    echo "   APT sigue ocupado. Intento educado de parar timers y diarios..."
    systemctl stop apt-daily.service apt-daily.timer apt-daily-upgrade.service apt-daily-upgrade.timer || true
    # Espera breve más
    sleep 5
  fi
}

# --- Parámetros/constantes ---
TARGET_USER="${SUDO_USER:-pi}"
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
RELEASES_DIR="/opt/bascula/releases"
APP_DIR="/opt/bascula/current"
VENV_DIR="$APP_DIR/.venv"
CFG_DIR="$TARGET_HOME/.bascula"
DATA_DIR="$CFG_DIR/data"
LOG_DIR="$CFG_DIR/logs"
APP_LOG="$TARGET_HOME/app.log"

# --- Comprobaciones previas ---
if [[ $EUID -ne 0 ]]; then
  echo "Ejecuta este script con sudo (sudo ./scripts/install-all.sh)" >&2
  exit 1
fi

apt_wait
echo "==> Instalando paquetes del sistema (incluye python3-tk) ..."
DEBIAN_FRONTEND=noninteractive apt-get update -y
# Notas 'N:' sobre cambio de suite (stable -> oldstable) son informativas.
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3 python3-pip python3-venv python3-tk \
  git rsync xserver-xorg xinit \
  unclutter-xfixes fonts-dejavu fonts-noto-color-emoji

# Picamera2 (si se usa cámara; no falla si no existe)
DEBIAN_FRONTEND=noninteractive apt-get install -y python3-picamera2 || true

echo "==> Creando estructura de releases en ${RELEASES_DIR} ..."
mkdir -p "$RELEASES_DIR"
# Copiamos el repo actual a una release local (vlocal)
rsync -a --delete --exclude ".git" ./ "${RELEASES_DIR}/vlocal/"
ln -sfn "${RELEASES_DIR}/vlocal" "$APP_DIR"

echo "==> Asegurando carpetas de datos en ${CFG_DIR} ..."
install -d -m 700 "$CFG_DIR"
install -d -m 700 "$DATA_DIR"
install -d -m 700 "$LOG_DIR"

# Config.json por defecto si no existe
if [[ ! -f "$CFG_DIR/config.json" ]]; then
  cat > "$CFG_DIR/config.json" <<'JSON'
{
  "port": "/dev/serial0",
  "baud": 115200,
  "calib_factor": 1.0,
  "smoothing": 10,
  "decimals": 1,
  "no_emoji": false
}
JSON
  chmod 600 "$CFG_DIR/config.json"
fi

echo "==> Preparando entorno virtual en ${VENV_DIR} ..."
if [[ ! -x "$VENV_DIR/bin/python3" ]]; then
  python3 -m venv "$VENV_DIR" --system-site-packages
  "$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel
fi

if [[ -f "$APP_DIR/requirements.txt" ]]; then
  "$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt"
fi

echo "==> Corrigiendo scripts/safe_run.sh ..."
SAFE_RUN="$APP_DIR/scripts/safe_run.sh"
if [[ ! -f "$SAFE_RUN" ]]; then
  # Creamos un safe_run.sh mínimo correcto
  mkdir -p "$APP_DIR/scripts"
  cat > "$SAFE_RUN" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
APP_DIR="/opt/bascula/current"
PY="$APP_DIR/.venv/bin/python3"
RECOVERY_FLAG="/var/lib/bascula-updater/force_recovery"
ALIVE="/run/bascula.alive"
export PYTHONUNBUFFERED=1
cd "$APP_DIR"
export PYTHONPATH="$APP_DIR:${PYTHONPATH:-}"

if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3)"
fi

smoke_test() { [[ -r "$APP_DIR/main.py" ]]; }

run_recovery() { exec "$PY" -m bascula.ui.recovery_ui; }

if [[ -f "$RECOVERY_FLAG" ]] || ! smoke_test; then
  run_recovery
fi

if [[ -f "$ALIVE" ]]; then
  now=$(date +%s); last=$(stat -c %Y "$ALIVE" 2>/dev/null || echo 0)
  (( now - last > 15 )) && run_recovery
fi

exec "$PY" "$APP_DIR/main.py"
SH
  chmod +x "$SAFE_RUN"
fi

# Parche: asegura cd + PYTHONPATH dentro de safe_run.sh si no estuvieran
grep -q 'cd "$APP_DIR"' "$SAFE_RUN" || sed -i '1 a cd "$APP_DIR"' "$SAFE_RUN"
grep -q 'PYTHONPATH=' "$SAFE_RUN" || sed -i '1 a export PYTHONPATH="$APP_DIR:${PYTHONPATH:-}"' "$SAFE_RUN"

# Permisos correctos para el usuario objetivo
chown "$TARGET_USER:$TARGET_USER" "$SAFE_RUN"
chmod +x "$SAFE_RUN"

echo "==> Creando ~/.xinitrc para lanzar la app vía X ..."
XINITRC="$TARGET_HOME/.xinitrc"
cat > "$XINITRC" <<XRC
#!/usr/bin/env bash
set -e
xset -dpms
xset s off
xset s noblank
unclutter -idle 0 -root &
exec /opt/bascula/current/scripts/safe_run.sh >> "$APP_LOG" 2>&1
XRC
chown "$TARGET_USER:$TARGET_USER" "$XINITRC"
chmod +x "$XINITRC"

echo "==> Creando servicio systemd bascula-app.service ..."
cat > /etc/systemd/system/bascula-app.service <<UNIT
[Unit]
Description=Bascula Digital Pro (kiosk)
After=network-online.target
Wants=network-online.target
Conflicts=getty@tty1.service

[Service]
User=${TARGET_USER}
Environment="BASCULA_CFG_DIR=${TARGET_HOME}/.bascula"
WorkingDirectory=${TARGET_HOME}
TTYPath=/dev/tty1
StandardInput=tty
PAMName=login
Restart=always
RestartSec=2
# Lanzamos X y .xinitrc del usuario
ExecStart=/usr/bin/xinit ${TARGET_HOME}/.xinitrc -- :0 vt1 -keeptty

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable bascula-app.service

echo "==> Ajustando permisos de /opt/bascula ..."
chown -R "$TARGET_USER:$TARGET_USER" "$RELEASES_DIR" || true
chown -h "$TARGET_USER:$TARGET_USER" "$APP_DIR" || true

echo "==> Instalación completada."
echo " - Directorio actual: $APP_DIR"
echo " - Venv: $VENV_DIR"
echo " - Config: $CFG_DIR/config.json"
echo " - Logs: $LOG_DIR  (app: $APP_LOG)"
echo " - Servicio: bascula-app.service (usa xinit + .xinitrc)"
echo "Reinicia o ejecuta: sudo systemctl restart bascula-app.service"

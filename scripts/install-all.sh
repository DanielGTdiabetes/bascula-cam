#!/usr/bin/env bash
# install-all.sh — Instalador robusto para Báscula Digital Pro
#
# Características clave:
# - Copia SIEMPRE desde la raíz real del repo (REPO_ROOT), no desde ./
# - Dinámico respecto al usuario ($TARGET_USER/$TARGET_HOME) en systemd y rutas
# - Espera educadamente los locks de APT/DPKG antes de instalar
# - Prepara /opt/bascula/releases y symlink /opt/bascula/current
# - Crea venv e instala requirements.txt
# - Crea ~/.bascula/{data,logs} y config.json si no existe
# - Garantiza scripts/safe_run.sh (con cd + PYTHONPATH) y ~/.xinitrc
# - Crea y habilita el servicio systemd
# - Defensivo: si faltan bascula/services/{storage.py,logging.py}, crea versiones mínimas
#
# Uso recomendado (desde la raíz del repo):
#   sudo ./scripts/install-all.sh
#
set -Eeuo pipefail

on_err() {
  echo "Error en línea $1 (código ${2:-1}). Abortando." >&2
}
trap 'on_err ${LINENO} $?' ERR

apt_wait() {
  echo "==> Comprobando si APT/DPKG están ocupados..."
  local tries=60
  while (( tries > 0 )); do
    if fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 || \
       fuser /var/lib/apt/lists/lock >/dev/null 2>&1 || \
       pgrep -x apt >/dev/null || pgrep -x apt-get >/dev/null || pgrep -x dpkg >/dev/null; then
      echo "   APT/DPKG ocupados; esperando 3s... (quedan $tries)"
      sleep 3
      ((tries--))
    else
      break
    fi
  done
  if (( tries == 0 )); then
    echo "   APT sigue ocupado. Intento educado de parar timers..."
    systemctl stop apt-daily.service apt-daily.timer apt-daily-upgrade.service apt-daily-upgrade.timer || true
    sleep 5
  fi
}

# --- Parámetros/constantes ---
TARGET_USER="${SUDO_USER:-pi}"
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
REPO_ROOT="$(cd "$(dirname "$0")/.."; pwd)"
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

if [[ ! -f "$REPO_ROOT/main.py" ]] || [[ ! -d "$REPO_ROOT/bascula" ]]; then
  echo "ERROR: No se detecta la raíz del repo correctamente en REPO_ROOT=$REPO_ROOT" >&2
  echo "Asegúrate de ejecutar: sudo ./scripts/install-all.sh desde la RAÍZ del repo." >&2
  exit 2
fi

# --- Instalación de paquetes ---
apt_wait
echo "==> Instalando paquetes del sistema (incluye python3-tk) ..."
DEBIAN_FRONTEND=noninteractive apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3 python3-pip python3-venv python3-tk \
  git rsync xserver-xorg xinit \
  unclutter-xfixes fonts-dejavu fonts-noto-color-emoji
DEBIAN_FRONTEND=noninteractive apt-get install -y python3-picamera2 || true

# --- Copia de la app a /opt/bascula/releases/vlocal y symlink ---
echo "==> Creando estructura de releases en ${RELEASES_DIR} ..."
mkdir -p "$RELEASES_DIR"
rsync -a --delete --exclude ".git" "$REPO_ROOT"/ "${RELEASES_DIR}/vlocal/"
ln -sfn "${RELEASES_DIR}/vlocal" "$APP_DIR"

# --- Directorios de datos y config ---
echo "==> Asegurando carpetas de datos en ${CFG_DIR} ..."
install -d -m 700 "$CFG_DIR" "$DATA_DIR" "$LOG_DIR"
# config.json por defecto si no existe
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

# --- Entorno virtual ---
echo "==> Preparando entorno virtual en ${VENV_DIR} ..."
if [[ ! -x "$VENV_DIR/bin/python3" ]]; then
  python3 -m venv "$VENV_DIR" --system-site-packages
  "$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel
fi
if [[ -f "$APP_DIR/requirements.txt" ]]; then
  "$VENV_DIR/bin/pip" install -r "$APP_DIR/requirements.txt"
fi

# --- scripts/safe_run.sh ---
echo "==> Garantizando scripts/safe_run.sh ..."
SAFE_RUN="$APP_DIR/scripts/safe_run.sh"
mkdir -p "$APP_DIR/scripts"
if [[ ! -f "$SAFE_RUN" ]]; then
  cat > "$SAFE_RUN" <<'SR'
#!/usr/bin/env bash
set -euo pipefail
APP_DIR="/opt/bascula/current"
PY="$APP_DIR/.venv/bin/python3"
RECOVERY_FLAG="/var/lib/bascula-updater/force_recovery"
ALIVE="/run/bascula.alive"
export PYTHONUNBUFFERED=1
cd "$APP_DIR"
export PYTHONPATH="$APP_DIR:${PYTHONPATH:-}"
if [[ ! -x "$PY" ]]; then PY="$(command -v python3)"; fi
smoke_test(){ [[ -r "$APP_DIR/main.py" ]]; }
run_recovery(){ exec "$PY" -m bascula.ui.recovery_ui; }
if [[ -f "$RECOVERY_FLAG" ]] || ! smoke_test; then run_recovery; fi
if [[ -f "$ALIVE" ]]; then now=$(date +%s); last=$(stat -c %Y "$ALIVE" 2>/dev/null || echo 0); (( now - last > 15 )) && run_recovery; fi
exec "$PY" "$APP_DIR/main.py"
SR
fi
# Garantiza cd + PYTHONPATH aunque el archivo ya existiese
grep -q 'cd "$APP_DIR"' "$SAFE_RUN" || sed -i '1 a cd "$APP_DIR"' "$SAFE_RUN"
grep -q 'PYTHONPATH=' "$SAFE_RUN" || sed -i '1 a export PYTHONPATH="$APP_DIR:${PYTHONPATH:-}"' "$SAFE_RUN"
chown "$TARGET_USER:$TARGET_USER" "$SAFE_RUN"
chmod +x "$SAFE_RUN"

# --- ~/.xinitrc ---
echo "==> Creando/actualizando ~/.xinitrc ..."
XINITRC="$TARGET_HOME/.xinitrc"
cat > "$XINITRC" <<'XRC'
#!/usr/bin/env bash
set -e
xset -dpms
xset s off
xset s noblank
unclutter -idle 0 -root &
exec /opt/bascula/current/scripts/safe_run.sh >> "$HOME/app.log" 2>&1
XRC
chown "$TARGET_USER:$TARGET_USER" "$XINITRC"
chmod +x "$XINITRC"

# --- Servicio systemd ---
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
ExecStart=/usr/bin/xinit ${TARGET_HOME}/.xinitrc -- :0 vt1 -keeptty

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable bascula-app.service

# --- Defensivo: crear módulos mínimos si faltan ---
echo "==> Revisión defensiva de módulos (storage.py, logging.py) ..."
if [[ ! -f "$APP_DIR/bascula/services/storage.py" ]]; then
  install -d "$APP_DIR/bascula/services"
  cat > "$APP_DIR/bascula/services/storage.py" <<'PY'
import json, csv, logging
from datetime import datetime
from pathlib import Path
BASCULA_DIR = Path.home()/".bascula"; DATA_DIR = BASCULA_DIR/"data"; LOG_DIR = BASCULA_DIR/"logs"
CONFIG_FILE = BASCULA_DIR/"config.json"; HISTORY_FILE = DATA_DIR/"history.csv"
for d in (BASCULA_DIR, DATA_DIR, LOG_DIR): d.mkdir(parents=True, exist_ok=True)
logging.getLogger("bascula.storage")
def _dump(p, data): p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
def _load(p, default=None):
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return default
DEFAULT_CONFIG={"port":"/dev/serial0","baud":115200,"calib_factor":1.0,"smoothing":10,"decimals":1,"no_emoji":False}
def load_config():
    if not CONFIG_FILE.exists(): _dump(CONFIG_FILE, DEFAULT_CONFIG); return DEFAULT_CONFIG
    return _load(CONFIG_FILE, DEFAULT_CONFIG)
def save_config(cfg): _dump(CONFIG_FILE, cfg)
def append_csv(weight_g, item="", meal_id=""):
    is_new=not HISTORY_FILE.exists()
    with HISTORY_FILE.open("a", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=["timestamp","weight_g","item","meal_id"])
        if is_new: w.writeheader()
        w.writerow({"timestamp": datetime.now().isoformat(), "weight_g": weight_g, "item": item, "meal_id": meal_id})
PY
fi
if [[ ! -f "$APP_DIR/bascula/services/logging.py" ]]; then
  cat > "$APP_DIR/bascula/services/logging.py" <<'PY'
import logging, sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
LOG_DIR = Path.home()/".bascula"/"logs"; LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR/"bascula.log"
def setup_logging(level=logging.INFO):
    logger=logging.getLogger("bascula"); logger.setLevel(level)
    if logger.handlers: return logger
    fmt=logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%%Y-%%m-%%d %%H:%%M:%%S")
    fh=RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"); fh.setFormatter(fmt); logger.addHandler(fh)
    ch=logging.StreamHandler(sys.stderr); ch.setFormatter(fmt); logger.addHandler(ch)
    logger.info("Logging inicializado"); return logger
PY
fi
chown -R "$TARGET_USER:$TARGET_USER" "$APP_DIR/bascula/services" || true

# --- Permisos en /opt/bascula y app.log inicial ---
echo "==> Ajustando permisos y creando app.log ..."
chown -R "$TARGET_USER:$TARGET_USER" "$RELEASES_DIR" || true
chown -h "$TARGET_USER:$TARGET_USER" "$APP_DIR" || true
touch "$APP_LOG"
chown "$TARGET_USER:$TARGET_USER" "$APP_LOG"

# --- Verificaciones finales (sanity checks) ---
echo "==> Verificaciones finales:"
[[ -f "$APP_DIR/main.py" ]] && echo "  ✔ main.py OK" || { echo "  ✖ FALTA $APP_DIR/main.py"; exit 3; }
[[ -d "$APP_DIR/bascula" ]] && echo "  ✔ paquete bascula/ OK" || { echo "  ✖ FALTA $APP_DIR/bascula/"; exit 3; }
[[ -x "$SAFE_RUN" ]] && echo "  ✔ safe_run.sh OK" || { echo "  ✖ safe_run.sh no ejecutable"; exit 3; }
[[ -f "$XINITRC" ]] && echo "  ✔ ~/.xinitrc OK" || { echo "  ✖ FALTA $XINITRC"; exit 3; }
systemctl cat bascula-app.service >/dev/null 2>&1 && echo "  ✔ servicio systemd creado" || { echo "  ✖ servicio systemd no creado"; exit 3; }

echo "==> Instalación completada."
echo " - Directorio actual: $APP_DIR"
echo " - Venv: $VENV_DIR"
echo " - Config: $CFG_DIR/config.json"
echo " - Logs: $LOG_DIR  (app: $APP_LOG)"
echo " - Servicio: bascula-app.service (usa xinit + .xinitrc)"
echo "Reinicia o ejecuta: sudo systemctl restart bascula-app.service"

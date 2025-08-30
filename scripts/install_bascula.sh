#!/usr/bin/env bash
set -euo pipefail

# =========================
# Configuración
# =========================
REPO_URL="https://github.com/DanielGTdiabetes/bascula-cam.git"
APP_DIR="/home/pi/bascula-cam"             # Se reescribe si el usuario no es 'pi'
SERVICE_NAME="bascula.service"
PI_USER="${SUDO_USER:-${USER}}"
HOME_DIR="$(getent passwd "$PI_USER" | cut -d: -f6)"
APP_DIR="${HOME_DIR}/bascula-cam"
VENV_DIR="${APP_DIR}/.venv"
PY_LOG="${HOME_DIR}/app.log"
PY_ENTRY="${APP_DIR}/main.py"              # Cambia aquí si tu entrypoint es otro
PYTHONPATH_VAL="${APP_DIR}"

# =========================
# Comprobaciones
# =========================
if [[ $EUID -ne 0 ]]; then
  echo "Por favor, ejecuta como root: sudo bash install_bascula.sh"
  exit 1
fi

echo "==> Usuario detectado: ${PI_USER}"
echo "==> HOME: ${HOME_DIR}"
echo "==> APP_DIR: ${APP_DIR}"

# =========================
# Paquetes del sistema
# =========================
echo "==> Actualizando e instalando paquetes necesarios..."
apt-get update -y
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  git python3 python3-venv python3-pip python3-tk \
  xserver-xorg xinit x11-xserver-utils \
  fonts-dejavu unclutter \
  libatlas-base-dev \
  # Opcionales para cámara (puedes comentarlos si no los necesitas ahora)
  python3-picamera2 libcamera-apps

# =========================
# Clonado / actualización del repositorio
# =========================
if [[ -d "${APP_DIR}/.git" ]]; then
  echo "==> Repo existente. Haciendo git pull..."
  sudo -u "${PI_USER}" bash -lc "cd '${APP_DIR}' && git fetch --all && git reset --hard origin/main && git pull --ff-only"
else
  echo "==> Clonando repositorio..."
  sudo -u "${PI_USER}" bash -lc "git clone --depth 1 '${REPO_URL}' '${APP_DIR}'"
fi

# =========================
# Virtualenv + dependencias
# =========================
echo "==> Creando entorno virtual e instalando requirements (si existen)..."
sudo -u "${PI_USER}" bash -lc "python3 -m venv '${VENV_DIR}'"
sudo -u "${PI_USER}" bash -lc "source '${VENV_DIR}/bin/activate' && \
  pip install --upgrade pip && \
  if [[ -f '${APP_DIR}/requirements.txt' ]]; then pip install -r '${APP_DIR}/requirements.txt'; else echo 'No hay requirements.txt, continuando...'; fi"

# =========================
# Script lanzador en consola (alias rápido)
# =========================
echo "==> Creando lanzador /usr/local/bin/bascula ..."
cat >/usr/local/bin/bascula <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
PI_USER="${SUDO_USER:-${USER}}"
HOME_DIR="$(getent passwd "$PI_USER" | cut -d: -f6)"
APP_DIR="${HOME_DIR}/bascula-cam"
VENV_DIR="${APP_DIR}/.venv"
PY_ENTRY="${APP_DIR}/main.py"
PY_LOG="${HOME_DIR}/app.log"
export PYTHONPATH="${APP_DIR}"
cd "${APP_DIR}"
# Oculta el cursor si hay X en marcha
if command -v unclutter >/dev/null 2>&1; then
  pgrep -x unclutter >/dev/null || (unclutter -idle 0.1 -root >/dev/null 2>&1 &)
fi
source "${VENV_DIR}/bin/activate"
exec python3 "${PY_ENTRY}" >> "${PY_LOG}" 2>&1
EOF
chmod +x /usr/local/bin/bascula

# Añadir alias en .bashrc si no existe
if ! sudo -u "${PI_USER}" grep -q 'alias bascula=' "${HOME_DIR}/.bashrc"; then
  echo "alias bascula='/usr/local/bin/bascula'" >> "${HOME_DIR}/.bashrc"
fi

# =========================
# Sesión X mínima (xinit) sin escritorio
# =========================
echo "==> Creando sesión X mínima /usr/local/bin/bascula-xsession ..."
cat >/usr/local/bin/bascula-xsession <<'EOF'
#!/usr/bin/env bash
# Sesión X mínima para lanzar la app
# Desactiva ahorro de energía y pantallazo negro
xset -dpms
xset s off
xset s noblank
# Oculta el cursor si está disponible
if command -v unclutter >/dev/null 2>&1; then
  pgrep -x unclutter >/dev/null || (unclutter -idle 0.1 -root >/dev/null 2>&1 &)
fi
# Ejecuta la app
exec /usr/local/bin/bascula
EOF
chmod +x /usr/local/bin/bascula-xsession

# ~/.xinitrc (para startx sin parámetros)
echo "==> Escribiendo ~/.xinitrc por si ejecutas startx sin comando..."
sudo -u "${PI_USER}" tee "${HOME_DIR}/.xinitrc" >/dev/null <<'EOF'
#!/bin/sh
xset -dpms
xset s off
xset s noblank
if command -v unclutter >/dev/null 2>&1; then
  pgrep -x unclutter >/dev/null || (unclutter -idle 0.1 -root >/dev/null 2>&1 &)
fi
exec /usr/local/bin/bascula
EOF
chown "${PI_USER}:${PI_USER}" "${HOME_DIR}/.xinitrc"
chmod +x "${HOME_DIR}/.xinitrc"

# =========================
# Servicio systemd para arrancar en boot
# =========================
echo "==> Creando servicio systemd ${SERVICE_NAME} ..."
cat >/etc/systemd/system/${SERVICE_NAME} <<EOF
[Unit]
Description=Bascula Digital Pro (Xinit autostart)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${PI_USER}
WorkingDirectory=${APP_DIR}
Environment=PYTHONPATH=${PYTHONPATH_VAL}
ExecStart=/usr/bin/startx /usr/local/bin/bascula-xsession -- -nocursor
Restart=on-failure
RestartSec=3

# Asegura que el DISPLAY se fije en :0 para librerías GUI
Environment=DISPLAY=:0

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"

# =========================
# Script de actualización + reinicio del servicio
# =========================
echo "==> Creando /usr/local/bin/bascula-update ..."
cat >/usr/local/bin/bascula-update <<EOF
#!/usr/bin/env bash
set -euo pipefail
PI_USER="${PI_USER}"
APP_DIR="${APP_DIR}"
VENV_DIR="${VENV_DIR}"
SERVICE_NAME="${SERVICE_NAME}"
sudo -u "\${PI_USER}" bash -lc "cd '\${APP_DIR}' && git fetch --all && git reset --hard origin/main && git pull --ff-only"
sudo -u "\${PI_USER}" bash -lc "source '\${VENV_DIR}/bin/activate' && if [[ -f '\${APP_DIR}/requirements.txt' ]]; then pip install -r '\${APP_DIR}/requirements.txt'; fi"
sudo systemctl restart "\${SERVICE_NAME}"
echo "Actualizado y reiniciado."
EOF
chmod +x /usr/local/bin/bascula-update

# =========================
# Permisos del log
# =========================
touch "${PY_LOG}"
chown "${PI_USER}:${PI_USER}" "${PY_LOG}"

echo "==> Instalación completada."
echo "Comandos útiles:"
echo "  • Iniciar ahora:     sudo systemctl start ${SERVICE_NAME}"
echo "  • Ver estado:        systemctl status ${SERVICE_NAME} -n 50"
echo "  • Logs en vivo:      journalctl -u ${SERVICE_NAME} -f"
echo "  • Ejecutar manual:   sudo -u ${PI_USER} startx    (o simplemente 'bascula' si ya tienes una X en marcha)"
echo "  • Alias rápido:      bascula"
echo "  • Actualizar código: sudo /usr/local/bin/bascula-update"

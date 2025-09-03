#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Rollback a arranque minimalista Xorg + Tk (sin LightDM/Openbox)
# Versión fija para usuario 'bascula' y proyecto en /home/bascula/bascula-cam
# - Deshabilita/purga LightDM y Openbox
# - Autologin en TTY1 para 'bascula'
# - Instala unclutter-xfixes
# - Crea/actualiza /home/bascula/.bash_profile (startx -- -nocursor en TTY1)
# - Crea/actualiza /home/bascula/.xinitrc (xset, fondo negro, ejecuta main.py y loguea)
# - Limpia restos de Openbox en el home de 'bascula'
# - Logs: /home/bascula/app_main.log
# ============================================================

TARGET_USER="bascula"
TARGET_HOME="/home/${TARGET_USER}"
PROJECT_DIR="${TARGET_HOME}/bascula-cam"    # <-- ruta del repo
PYTHONPATH_DIR="${PROJECT_DIR}"              # para que importe desde la raíz del repo
APP_ENTRY="${PROJECT_DIR}/main.py"
APP_LOG="${TARGET_HOME}/app_main.log"

LOG="[rollback_to_startx]"

if [[ ! -d "${TARGET_HOME}" ]]; then
  echo "${LOG} ERROR: No existe el home ${TARGET_HOME}. Crea el usuario 'bascula' y/o su HOME." >&2
  exit 1
fi

echo "${LOG} Usuario objetivo: ${TARGET_USER} (${TARGET_HOME})"
echo "${LOG} Proyecto esperado en: ${PROJECT_DIR}"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "${LOG} Necesito '$1' instalado."; exit 1; }
}

require_cmd systemctl
require_cmd tee
require_cmd awk
require_cmd sed

# 1) Deshabilitar LightDM si existe
if systemctl list-unit-files | grep -q "^lightdm.service"; then
  echo "${LOG} Deshabilitando LightDM..."
  sudo systemctl disable lightdm --now || true
else
  echo "${LOG} LightDM no está instalado o no tiene unit file."
fi

# 2) (Opcional) Purga de LightDM/Openbox
PURGE_PACKAGES=1  # pon a 0 si prefieres no purgar
EXIST_LDM=$(dpkg -l 2>/dev/null | awk '{print $2}' | grep -xq lightdm && echo 1 || echo 0)
EXIST_OBX=$(dpkg -l 2>/dev/null | awk '{print $2}' | grep -xq openbox && echo 1 || echo 0)
if [[ "$PURGE_PACKAGES" -eq 1 ]] && ([[ "$EXIST_LDM" -eq 1 ]] || [[ "$EXIST_OBX" -eq 1 ]]); then
  echo "${LOG} Purga de LightDM/Openbox..."
  sudo apt-get update -y
  sudo apt-get purge -y lightdm openbox openbox-menu obconf || true
  sudo apt-get autoremove -y || true
else
  echo "${LOG} Saltando purga de paquetes (configurado para no purgar o no instalados)."
fi

# 3) Autologin en TTY1 para 'bascula'
echo "${LOG} Configurando autologin en TTY1 para ${TARGET_USER}..."
sudo mkdir -p /etc/systemd/system/getty@tty1.service.d
sudo tee /etc/systemd/system/getty@tty1.service.d/override.conf >/dev/null <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin ${TARGET_USER} --noclear %I \$TERM
Type=idle
EOF
sudo systemctl daemon-reload
sudo systemctl restart getty@tty1

# 4) Instalar unclutter-xfixes para ocultar puntero
echo "${LOG} Instalando unclutter-xfixes..."
sudo apt-get update -y
sudo apt-get install -y unclutter-xfixes

# 5) ~/.bash_profile de 'bascula'
BASH_PROFILE="${TARGET_HOME}/.bash_profile"
echo "${LOG} Escribiendo ${BASH_PROFILE}..."
sudo tee "${BASH_PROFILE}" >/dev/null <<'EOF'
# ~/.bash_profile – arranca Xorg minimalista en TTY1 sin cursor
# Ejecuta startx sólo si no hay DISPLAY y estamos en /dev/tty1
if [[ -z "$DISPLAY" ]] && [[ "$(tty)" == "/dev/tty1" ]]; then
  exec startx -- -nocursor
fi
EOF
sudo chown "${TARGET_USER}:${TARGET_USER}" "${BASH_PROFILE}"
sudo chmod 0644 "${BASH_PROFILE}"

# 6) ~/.xinitrc de 'bascula' (lanza la app)
XINITRC="${TARGET_HOME}/.xinitrc"
echo "${LOG} Escribiendo ${XINITRC}..."
sudo tee "${XINITRC}" >/dev/null <<EOF
#!/bin/sh
# ~/.xinitrc – sesión X minimalista para kiosco Tk

# Evita apagado de pantalla y “screensaver”
xset -dpms
xset s off
xset s noblank

# Fondo negro (evita flash blanco)
xsetroot -solid black

# Ocultar puntero (refuerza el -nocursor de startx)
unclutter -idle 0 -root &

# PYTHONPATH para el proyecto
export PYTHONPATH=${PYTHONPATH_DIR}

# Lanza la app y deja log
python3 ${APP_ENTRY} >> ${APP_LOG} 2>&1
EOF
sudo chown "${TARGET_USER}:${TARGET_USER}" "${XINITRC}"
sudo chmod +x "${XINITRC}"

# 7) Limpieza de Openbox en el HOME de 'bascula'
echo "${LOG} Limpieza de autostarts de Openbox si quedaran..."
sudo rm -f "${TARGET_HOME}/.config/openbox/autostart" || true
sudo rm -rf "${TARGET_HOME}/.config/openbox" || true
sudo rm -rf /etc/xdg/openbox || true

# 8) Verificaciones
echo "${LOG} Verificaciones:"
echo -n "  - getty@tty1 override: "
[[ -f /etc/systemd/system/getty@tty1.service.d/override.conf ]] && echo "OK" || echo "FALTA"
echo -n "  - ${BASH_PROFILE}: "
[[ -f "${BASH_PROFILE}" ]] && echo "OK" || echo "FALTA"
echo -n "  - ${XINITRC}: "
[[ -f "${XINITRC}" ]] && echo "OK" || echo "FALTA"
echo -n "  - unclutter-xfixes: "
dpkg -l | awk '{print $2}' | grep -qx unclutter-xfixes && echo "OK" || echo "FALTA"

# 9) Avisos útiles
if [[ ! -f "${APP_ENTRY}" ]]; then
  echo
  echo "${LOG} ATENCIÓN: No encuentro ${APP_ENTRY}."
  echo "  - Asegúrate de que el repo está en ${PROJECT_DIR} y que existe main.py."
  echo "  - Si tu ruta es distinta, edita ${XINITRC} y corrige APP_ENTRY/PYTHONPATH."
fi

echo
echo "${LOG} Listo. Reinicia para probar:"
echo "  sudo reboot"
echo
echo "Después: autologin (bascula) → startx (sin cursor) → Tk fullscreen."
echo "Log de la app: ${APP_LOG}"

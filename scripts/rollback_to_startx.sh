#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Rollback a arranque minimalista Xorg + Tk (sin LightDM/Openbox)
# - Deshabilita/purga LightDM y Openbox (opcional)
# - Autologin en TTY1 para el usuario actual
# - Instala unclutter-xfixes
# - Crea/actualiza ~/.bash_profile con startx -- -nocursor en TTY1
# - Crea/actualiza ~/.xinitrc minimalista que lanza la app y desactiva saver/DPMS
# - Deja logs en /home/<user>/app_main.log
# ============================================================

USER_NAME="${SUDO_USER:-${USER}}"
USER_HOME="$(eval echo "~${USER_NAME}")"
LOG="# [rollback_to_startx]"

echo "$LOG Usuario objetivo: ${USER_NAME} (${USER_HOME})"

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "$LOG Necesito '$1' instalado."; exit 1; }
}

require_cmd systemctl
require_cmd tee
require_cmd awk
require_cmd sed

# 1) Detener y deshabilitar LightDM si existe
if systemctl list-unit-files | grep -q "^lightdm.service"; then
  echo "$LOG Deshabilitando LightDM..."
  sudo systemctl disable lightdm --now || true
else
  echo "$LOG LightDM no está instalado o no tiene unit file."
fi

# 2) Desinstalar Openbox y LightDM (opcional, seguro en Zero 2W por RAM)
PURGE_PACKAGES=0
if dpkg -l | awk '{print $2}' | grep -qx lightdm || dpkg -l | awk '{print $2}' | grep -qx openbox; then
  echo "$LOG Detectados paquetes lightdm/openbox instalados."
  # Cambia a 1 si quieres purgar automáticamente, o deja 0 para sólo deshabilitar
  PURGE_PACKAGES=1
fi

if [ "$PURGE_PACKAGES" -eq 1 ]; then
  echo "$LOG Purga de LightDM/Openbox (opcional habilitada en este script)..."
  sudo apt-get update -y
  sudo apt-get purge -y lightdm openbox openbox-menu obconf || true
  sudo apt-get autoremove -y || true
else
  echo "$LOG Saltando purga de paquetes (configurado para deshabilitar sin eliminar)."
fi

# 3) Autologin en TTY1 para el usuario
echo "$LOG Configurando autologin en TTY1 para ${USER_NAME}..."
sudo mkdir -p /etc/systemd/system/getty@tty1.service.d
sudo tee /etc/systemd/system/getty@tty1.service.d/override.conf >/dev/null <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin ${USER_NAME} --noclear %I \$TERM
Type=idle
EOF
sudo systemctl daemon-reload
sudo systemctl restart getty@tty1

# 4) Instalar unclutter-xfixes para ocultar puntero
echo "$LOG Instalando unclutter-xfixes..."
sudo apt-get update -y
sudo apt-get install -y unclutter-xfixes

# 5) Crear/actualizar ~/.bash_profile para lanzar X solo en TTY1
BASH_PROFILE="${USER_HOME}/.bash_profile"
echo "$LOG Escribiendo ${BASH_PROFILE}..."
sudo -u "${USER_NAME}" tee "${BASH_PROFILE}" >/dev/null <<'EOF'
# ~/.bash_profile — arranca Xorg minimalista en TTY1 sin cursor
# Ejecuta startx sólo si no hay DISPLAY y estamos en /dev/tty1
if [[ -z "$DISPLAY" ]] && [[ "$(tty)" == "/dev/tty1" ]]; then
  exec startx -- -nocursor
fi
EOF
sudo chown "${USER_NAME}:${USER_NAME}" "${BASH_PROFILE}"
sudo chmod 0644 "${BASH_PROFILE}"

# 6) Crear/actualizar ~/.xinitrc minimalista
XINITRC="${USER_HOME}/.xinitrc"
echo "$LOG Escribiendo ${XINITRC}..."
sudo -u "${USER_NAME}" tee "${XINITRC}" >/dev/null <<'EOF'
#!/bin/sh
# ~/.xinitrc — sesión X minimalista para kiosco Tk

# Evita apagado de pantalla y “screensaver”
xset -dpms
xset s off
xset s noblank

# Fondo negro (evita flash blanco)
xsetroot -solid black

# Ocultar puntero (refuerza el -nocursor de startx)
# Si no quieres usar unclutter, comenta la línea siguiente:
unclutter -idle 0 -root &

# PYTHONPATH necesario para el proyecto (ajusta si es distinto)
export PYTHONPATH=/home/pi/bascula-cam

# Lanza la app y deja log
python3 /home/pi/bascula-cam/main.py >> /home/pi/app_main.log 2>&1
EOF
sudo chown "${USER_NAME}:${USER_NAME}" "${XINITRC}"
sudo chmod +x "${XINITRC}"

# 7) Limpieza de restos de Openbox/autostart que puedan reinyectar cursor o saver
echo "$LOG Limpieza de autostarts de Openbox si quedaran..."
sudo rm -f "${USER_HOME}/.config/openbox/autostart" || true
sudo rm -rf "${USER_HOME}/.config/openbox" || true
sudo rm -rf /etc/xdg/openbox || true

# 8) Comprobaciones finales
echo "$LOG Verificaciones:"
echo -n "  - getty@tty1 override: "
if [ -f /etc/systemd/system/getty@tty1.service.d/override.conf ]; then echo "OK"; else echo "FALTA"; fi
echo -n "  - ~/.bash_profile: "
[ -f "${BASH_PROFILE}" ] && echo "OK" || echo "FALTA"
echo -n "  - ~/.xinitrc: "
[ -f "${XINITRC}" ] && echo "OK" || echo "FALTA"
echo -n "  - unclutter-xfixes: "
dpkg -l | awk '{print $2}' | grep -qx unclutter-xfixes && echo "OK" || echo "FALTA"

echo
echo "$LOG Listo. Reinicia para probar:"
echo "  sudo reboot"
echo
echo "Tras el reboot: autologin en TTY1 → startx (sin cursor) → tu app Tk."
echo "Logs de la app: ${USER_HOME}/app_main.log"

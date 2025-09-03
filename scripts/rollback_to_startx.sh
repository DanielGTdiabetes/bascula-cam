#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# Rollback a Xorg minimalista (sin LightDM/Openbox) con AUTODETECCIÓN
# - Usuario objetivo: arg1 si se pasa; si no, 'bascula' si existe; si no, usuario que ejecuta.
# - Proyecto: busca en /home/<usuario> rutas que contengan "bascula" y tengan un main.py
# - Configura autologin en TTY1
# - Instala unclutter-xfixes
# - Escribe ~/.bash_profile (startx -- -nocursor)
# - Escribe ~/.xinitrc (xset, fondo negro, ejecuta main.py y loguea)
# - Limpia restos de Openbox
# ============================================================

echo "[rollback] Iniciando..."

# ---------- Selección de usuario ----------
TARGET_USER_ARG="${1:-}"
if [[ -n "$TARGET_USER_ARG" ]]; then
  TARGET_USER="$TARGET_USER_ARG"
elif id -u bascula >/dev/null 2>&1; then
  TARGET_USER="bascula"
else
  TARGET_USER="${SUDO_USER:-${USER}}"
fi

TARGET_HOME="$(eval echo "~${TARGET_USER}")"

if [[ ! -d "$TARGET_HOME" ]]; then
  echo "[rollback] ERROR: El home de ${TARGET_USER} no existe: ${TARGET_HOME}" >&2
  exit 1
fi

echo "[rollback] Usuario objetivo: ${TARGET_USER} (${TARGET_HOME})"

# ---------- Funciones auxiliares ----------
require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "[rollback] Necesito '$1' instalado."; exit 1; }
}

require_cmd systemctl
require_cmd tee
require_cmd awk
require_cmd sed
require_cmd find

# ---------- Detectar carpeta de proyecto ----------
# Criterios:
# 1) Directorios bajo $TARGET_HOME que contengan 'bascula' en su nombre y tengan main.py a <=3 niveles
# 2) Si no hay, cualquier main.py a <=3 niveles bajo $TARGET_HOME
# 3) Fallback: $TARGET_HOME/bascula-cam si existe
echo "[rollback] Buscando proyecto bajo ${TARGET_HOME} ..."
PROJECT_DIR=""

while IFS= read -r -d '' d; do
  if find "$d" -maxdepth 3 -type f -name "main.py" | grep -q .; then
    PROJECT_DIR="$d"
    break
  fi
done < <(find "$TARGET_HOME" -maxdepth 2 -type d -iname "*bascula*" -print0 2>/dev/null)

if [[ -z "$PROJECT_DIR" ]]; then
  MP=$(find "$TARGET_HOME" -maxdepth 3 -type f -name "main.py" 2>/dev/null | head -n 1 || true)
  if [[ -n "$MP" ]]; then
    PROJECT_DIR="$(dirname "$MP")"
  fi
fi

if [[ -z "$PROJECT_DIR" ]] && [[ -d "$TARGET_HOME/bascula-cam" ]]; then
  PROJECT_DIR="$TARGET_HOME/bascula-cam"
fi

if [[ -z "$PROJECT_DIR" ]]; then
  echo "[rollback] ADVERTENCIA: No he encontrado el proyecto automáticamente."
  echo "[rollback] Puedes:"
  echo "  1) Clonar el repo en ${TARGET_HOME} (p.ej. ${TARGET_HOME}/bascula-cam)"
  echo "  2) Re-ejecutar este script indicando el usuario: sudo $0 ${TARGET_USER}"
  echo "  3) O editar luego ~/.xinitrc para fijar la ruta correcta"
  # Continuamos igualmente, pero .xinitrc quedará con una ruta placeholder.
  PROJECT_DIR="${TARGET_HOME}/bascula-cam"
  PLACEHOLDER=1
else
  PLACEHOLDER=0
fi

echo "[rollback] Proyecto detectado: ${PROJECT_DIR} (placeholder=${PLACEHOLDER})"

# ---------- Deshabilitar/Purgar LightDM y Openbox ----------
if systemctl list-unit-files | grep -q "^lightdm.service"; then
  echo "[rollback] Deshabilitando LightDM..."
  sudo systemctl disable lightdm --now || true
else
  echo "[rollback] LightDM no está habilitado."
fi

PURGE_PACKAGES=1  # cambia a 0 si prefieres NO purgar aunque existan
EXIST_LDM=$(dpkg -l 2>/dev/null | awk '{print $2}' | grep -xq lightdm && echo 1 || echo 0)
EXIST_OBX=$(dpkg -l 2>/dev/null | awk '{print $2}' | grep -xq openbox && echo 1 || echo 0)
if [[ "$PURGE_PACKAGES" -eq 1 ]] && ([[ "$EXIST_LDM" -eq 1 ]] || [[ "$EXIST_OBX" -eq 1 ]]); then
  echo "[rollback] Purga de LightDM/Openbox..."
  sudo apt-get update -y
  sudo apt-get purge -y lightdm openbox openbox-menu obconf || true
  sudo apt-get autoremove -y || true
else
  echo "[rollback] Saltando purga de paquetes (configurado para no purgar o no instalados)."
fi

# ---------- Autologin en TTY1 ----------
echo "[rollback] Configurando autologin en TTY1 para ${TARGET_USER}..."
sudo mkdir -p /etc/systemd/system/getty@tty1.service.d
sudo tee /etc/systemd/system/getty@tty1.service.d/override.conf >/dev/null <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin ${TARGET_USER} --noclear %I \$TERM
Type=idle
EOF
sudo systemctl daemon-reload
sudo systemctl restart getty@tty1

# ---------- Instalar unclutter-xfixes ----------
echo "[rollback] Instalando unclutter-xfixes..."
sudo apt-get update -y
sudo apt-get install -y unclutter-xfixes

# ---------- Escribir ~/.bash_profile ----------
BASH_PROFILE="${TARGET_HOME}/.bash_profile"
echo "[rollback] Escribiendo ${BASH_PROFILE} ..."
sudo -u "${TARGET_USER}" tee "${BASH_PROFILE}" >/dev/null <<'EOF'
# ~/.bash_profile — arranca Xorg minimalista en TTY1 sin cursor
# Ejecuta startx sólo si no hay DISPLAY y estamos en /dev/tty1
if [[ -z "$DISPLAY" ]] && [[ "$(tty)" == "/dev/tty1" ]]; then
  exec startx -- -nocursor
fi
EOF
sudo chown "${TARGET_USER}:${TARGET_USER}" "${BASH_PROFILE}"
sudo chmod 0644 "${BASH_PROFILE}"

# ---------- Escribir ~/.xinitrc ----------
XINITRC="${TARGET_HOME}/.xinitrc"
PYTHONPATH_DIR="$(dirname "${PROJECT_DIR}")"
APP_ENTRY="${PROJECT_DIR}/main.py"

echo "[rollback] Escribiendo ${XINITRC} ..."
sudo -u "${TARGET_USER}" tee "${XINITRC}" >/dev/null <<EOF
#!/bin/sh
# ~/.xinitrc — sesión X minimalista para kiosco Tk

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
python3 ${APP_ENTRY} >> ${TARGET_HOME}/app_main.log 2>&1
EOF
sudo chown "${TARGET_USER}:${TARGET_USER}" "${XINITRC}"
sudo chmod +x "${XINITRC}"

# ---------- Limpieza restos Openbox ----------
echo "[rollback] Limpiando restos Openbox/autostart..."
sudo rm -f "${TARGET_HOME}/.config/openbox/autostart" || true
sudo rm -rf "${TARGET_HOME}/.config/openbox" || true
sudo rm -rf /etc/xdg/openbox || true

# ---------- Verificaciones ----------
echo "[rollback] Verificaciones:"
echo -n "  - getty@tty1 override: "
[[ -f /etc/systemd/system/getty@tty1.service.d/override.conf ]] && echo "OK" || echo "FALTA"
echo -n "  - ${BASH_PROFILE}: "
[[ -f "${BASH_PROFILE}" ]] && echo "OK" || echo "FALTA"
echo -n "  - ${XINITRC}: "
[[ -f "${XINITRC}" ]] && echo "OK" || echo "FALTA"
echo -n "  - unclutter-xfixes: "
dpkg -l | awk '{print $2}' | grep -qx unclutter-xfixes && echo "OK" || echo "FALTA"

if [[ "$PLACEHOLDER" -eq 1 ]]; then
  echo
  echo "[rollback] IMPORTANTE: No se localizó el proyecto automáticamente."
  echo "  - Revisa/edita ${XINITRC} y pon la ruta correcta al main.py de tu proyecto."
  echo "  - O vuelve a ejecutar: sudo $0 ${TARGET_USER}"
fi

echo
echo "[rollback] Listo. Reinicia para probar:"
echo "  sudo reboot"
echo
echo "Tras el reboot: autologin (${TARGET_USER}) → startx (sin cursor) → tu app Tk."
echo "Logs de la app: ${TARGET_HOME}/app_main.log"

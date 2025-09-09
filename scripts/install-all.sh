#!/usr/bin/env bash
# install-all.sh — Instalador idempotente para Báscula Digital Pro
# - Crea directorios con propietario correcto (sin dejar nada como root en $HOME)
# - Prepara venv y dependencias como usuario destino
# - (Opcional) instala servicio systemd que corre como dicho usuario
# - Seguro ante re-ejecuciones

set -euo pipefail

#==============================#
# Utilidades y configuración   #
#==============================#

RED=$'\e[31m'; GRN=$'\e[32m'; YLW=$'\e[33m'; BLU=$'\e[34m'; NOC=$'\e[0m'
log() { printf "%s[install]%s %s\n" "$BLU" "$NOC" "$*"; }
ok()  { printf "%s[ok]%s %s\n"      "$GRN" "$NOC" "$*"; }
warn(){ printf "%s[warn]%s %s\n"    "$YLW" "$NOC" "$*"; }
err() { printf "%s[err ]%s %s\n"    "$RED" "$NOC" "$*" >&2; }

die() { err "$*"; exit 1; }

on_error() {
  err "Se produjo un error en la línea $1. Revisa la salida anterior."
}
trap 'on_error $LINENO' ERR

#==============================#
# Flags / argumentos           #
#==============================#
WITH_SYSTEMD=1
APT_UPDATE=1

usage() {
  cat <<EOF
Uso: sudo ./install-all.sh [opciones]

Opciones:
  --no-systemd         No instalar/activar servicio systemd
  --no-apt-update      No ejecutar apt-get update/upgrade
  -h, --help           Mostrar ayuda

Este script DEBE ejecutarse con sudo (root) porque instala paquetes
y crea unidades systemd, pero se asegura de NO dejar archivos en
el HOME con propietario root.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-systemd)   WITH_SYSTEMD=0; shift;;
    --no-apt-update)APT_UPDATE=0; shift;;
    -h|--help) usage; exit 0;;
    *) die "Opción no reconocida: $1";;
  case_esac_done=true; done
unset case_esac_done

#==============================#
# Detección de usuario destino #
#==============================#

if [[ "${EUID}" -ne 0 ]]; then
  die "Este script debe ejecutarse con sudo/root."
fi

# Estrategia segura para detectar el usuario real “de sesión”:
# 1) SUDO_USER si existe
# 2) logname si es razonable
# 3) quien ejecutó anteriormente (who am i) si aplica
# 4) fallback: pi (pero comprobando que existe)
TARGET_USER="${SUDO_USER:-}"
if [[ -z "${TARGET_USER}" ]]; then
  TARGET_USER="$(logname 2>/dev/null || true)"
fi
if [[ -z "${TARGET_USER}" || "${TARGET_USER}" == "root" ]]; then
  if id pi &>/dev/null; then
    TARGET_USER="pi"
    warn "No se pudo determinar SUDO_USER/logname; usando fallback TARGET_USER=pi"
  else
    die "No se pudo determinar el usuario destino y no existe 'pi'. Ejecuta con 'sudo -u <usuario>' o crea el usuario."
  fi
fi

# Comprueba que el usuario existe y obtiene home y grupo
TARGET_UID="$(id -u "${TARGET_USER}")"
TARGET_GID="$(id -g "${TARGET_USER}")"
TARGET_GROUP="$(id -gn "${TARGET_USER}")"
TARGET_HOME="$(getent passwd "${TARGET_USER}" | cut -d: -f6)"
[[ -n "${TARGET_HOME}" ]] || die "No se pudo resolver HOME de ${TARGET_USER}"

ok "Usuario destino: ${TARGET_USER} (uid=${TARGET_UID}, gid=${TARGET_GID})"
ok "HOME destino: ${TARGET_HOME}"

# Rutas del proyecto
REPO_DIR="${TARGET_HOME}/bascula-cam"
VENV_DIR="${REPO_DIR}/.venv"
STATE_DIR="${TARGET_HOME}/.bascula"
LOG_DIR="${STATE_DIR}/logs"
CONFIG_DIR="${TARGET_HOME}/.config/bascula"

#==============================#
# Helpers                      #
#==============================#

# Crea un directorio con dueño/grupo correctos desde el principio
mkuserdir() {
  local d="$1" mode="${2:-755}"
  install -d -m "${mode}" -o "${TARGET_USER}" -g "${TARGET_GROUP}" -- "${d}"
}

# Crea/actualiza archivo de texto con propietario correcto (si se pasa contenido)
write_user_file() {
  local path="$1"; shift
  local content="${1:-}"
  install -D -m 644 -o "${TARGET_USER}" -g "${TARGET_GROUP}" /dev/null "${path}"
  if [[ -n "${content}" ]]; then
    # Escribimos como root y corregimos propietario después (más simple)
    printf "%s" "${content}" > "${path}"
    chown "${TARGET_UID}:${TARGET_GID}" "${path}"
  fi
}

# Ejecuta un comando como el usuario destino (respetando su HOME/ENV)
run_as_user() {
  sudo -u "${TARGET_USER}" -H -- env HOME="${TARGET_HOME}" USER="${TARGET_USER}" "$@"
}

#==============================#
# APT: paquetes del sistema    #
#==============================#

if [[ "${APT_UPDATE}" -eq 1 ]]; then
  log "Actualizando índices APT…"
  apt-get update -y
fi

log "Instalando dependencias del sistema (mínimas)…"
DEBS=(
  python3 python3-venv python3-pip
  python3-dev build-essential
  git
)
apt-get install -y "${DEBS[@]}"

#==============================#
# Estructura de directorios    #
#==============================#

log "Creando estructura de directorios en HOME del usuario destino…"
mkuserdir "${REPO_DIR}" 755 || true   # por si ya existe (clonado previamente)
mkuserdir "${STATE_DIR}" 700
mkuserdir "${LOG_DIR}"   755
mkuserdir "${CONFIG_DIR}" 700

# Test de escritura en logs
run_as_user bash -c "echo ok > '${LOG_DIR}/.write_test' && rm -f '${LOG_DIR}/.write_test'"
ok "Directorio de logs escribible por ${TARGET_USER}: ${LOG_DIR}"

#==============================#
# Repositorio y venv           #
#==============================#

if [[ ! -d "${REPO_DIR}/.git" && -d "${REPO_DIR}" && -n "$(ls -A "${REPO_DIR}" 2>/dev/null)" ]]; then
  warn "El directorio ${REPO_DIR} no es un repo git pero contiene archivos. Continuando."
fi

if [[ ! -d "${VENV_DIR}" ]]; then
  log "Creando virtualenv en ${VENV_DIR} (propietario ${TARGET_USER})…"
  run_as_user python3 -m venv "${VENV_DIR}"
else
  ok "VENV ya existe: ${VENV_DIR}"
fi

# Actualiza pip y instala requirements si existe
if [[ -f "${REPO_DIR}/requirements.txt" ]]; then
  log "Instalando dependencias de Python…"
  run_as_user bash -c "source '${VENV_DIR}/bin/activate' && pip install --upgrade pip && pip install -r '${REPO_DIR}/requirements.txt'"
else
  warn "No se encontró requirements.txt en ${REPO_DIR}; omitiendo pip install."
fi

#==============================#
# Lanzador seguro (opcional)   #
#==============================#

SAFE_RUN="${REPO_DIR}/safe_run.sh"
write_user_file "${SAFE_RUN}" "#!/usr/bin/env bash
set -euo pipefail
export PYTHONUNBUFFERED=1
export LOGLEVEL=\${LOGLEVEL:-INFO}
export BASCULA_HOME=\"${STATE_DIR}\"
cd \"${REPO_DIR}\"
exec \"${VENV_DIR}/bin/python\" -X faulthandler \"${REPO_DIR}/main.py\"
"
chmod 755 "${SAFE_RUN}"
chown "${TARGET_UID}:${TARGET_GID}" "${SAFE_RUN}"
ok "Creado lanzador: ${SAFE_RUN}"

#==============================#
# Autostart (systemd opcional) #
#==============================#

UNIT_PATH="/etc/systemd/system/bascula.service"
if [[ "${WITH_SYSTEMD}" -eq 1 ]]; then
  log "Creando servicio systemd (${UNIT_PATH})…"
  cat > "${UNIT_PATH}" <<EOF
[Unit]
Description=Bascula Digital Pro
After=graphical.target network-online.target

[Service]
Type=simple
User=${TARGET_USER}
Group=${TARGET_GROUP}
WorkingDirectory=${REPO_DIR}
Environment=BASCULA_HOME=${STATE_DIR}
Environment=LOGLEVEL=INFO
ExecStart=${SAFE_RUN}
Restart=always
RestartSec=2
# Limpiar variables que podrían forzar X como root
Environment=DISPLAY=
Environment=XAUTHORITY=

[Install]
WantedBy=graphical.target
EOF

  systemctl daemon-reload
  systemctl enable bascula.service
  ok "Servicio habilitado: bascula.service"
else
  warn "Has desactivado --no-systemd. No se instala servicio."
fi

#==============================#
# Autostart Openbox (solo si NO hay systemd)
#==============================#

if [[ "${WITH_SYSTEMD}" -eq 0 ]]; then
  AUTOBOX="${TARGET_HOME}/.config/openbox/autostart"
  mkuserdir "$(dirname "${AUTOBOX}")" 755
  if [[ ! -f "${AUTOBOX}" ]]; then
    write_user_file "${AUTOBOX}" "#!/bin/sh
# Autostart de Openbox para Báscula (no usa sudo)
\"${SAFE_RUN}\" &
"
    chmod 744 "${AUTOBOX}"
    chown "${TARGET_UID}:${TARGET_GID}" "${AUTOBOX}"
    ok "Autostart Openbox creado en ${AUTOBOX}"
  else
    if ! grep -q "${SAFE_RUN}" "${AUTOBOX}"; then
      log "Añadiendo lanzador a autostart de Openbox…"
      echo "\"${SAFE_RUN}\" &" >> "${AUTOBOX}"
      chown "${TARGET_UID}:${TARGET_GID}" "${AUTOBOX}"
    fi
  fi
fi

#==============================#
# Validaciones de permisos     #
#==============================#

log "Validando propietarios de rutas clave…"
declare -a CHECK_DIRS=("${REPO_DIR}" "${STATE_DIR}" "${LOG_DIR}" "${CONFIG_DIR}")
for d in "${CHECK_DIRS[@]}"; do
  st="$(stat -c '%U:%G %A' "${d}")"
  echo " - ${d} -> ${st}"
done

#==============================#
# Mensaje final e instrucciones#
#==============================#

ok "Instalación completada sin dejar directorios del HOME como root."
echo
echo "Para ejecutar manualmente ahora (prueba rápida):"
echo "  sudo -u ${TARGET_USER} -H env HOME=${TARGET_HOME} ${SAFE_RUN}"
echo
if [[ "${WITH_SYSTEMD}" -eq 1 ]]; then
  echo "Para iniciar el servicio:"
  echo "  sudo systemctl start bascula.service"
  echo "Ver logs:"
  echo "  journalctl -u bascula -e --no-pager -n 200"
fi

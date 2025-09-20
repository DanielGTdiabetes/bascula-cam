#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  TARGET_USER="${TARGET_USER:-${SUDO_USER:-pi}}"
  exec sudo TARGET_USER="${TARGET_USER}" bash "$0" "$@"
fi

TARGET_USER="${TARGET_USER:-${SUDO_USER:-pi}}"

# Ejecuta la fase 2 principal (instalación de dependencias y app)
PHASE=2 TARGET_USER="${TARGET_USER}" bash "${SCRIPT_DIR}/install-all.sh" "$@"

# Asegura los unit files actualizados antes de arrancar
install -m 0644 "${ROOT_DIR}/systemd/bascula-web.service" /etc/systemd/system/
install -m 0644 "${ROOT_DIR}/systemd/bascula-app.service" /etc/systemd/system/
systemctl daemon-reload

# Prepara entorno de configuración y flags de readiness
install -d -m 0755 /etc/bascula
DEFAULT_FILE="/etc/default/bascula-web"
if [[ ! -f "${DEFAULT_FILE}" ]]; then
  cat <<'EOF' > "${DEFAULT_FILE}"
BASCULA_WEB_HOST=0.0.0.0
BASCULA_WEB_PORT=8080
EOF
  chmod 0644 "${DEFAULT_FILE}"
  chown root:root "${DEFAULT_FILE}"
fi
install -D -m 0644 /dev/null /etc/bascula/WEB_READY
install -D -m 0644 /dev/null /etc/bascula/APP_READY

# Asegura que los servicios estén parados antes de validar el puerto
systemctl stop bascula-web bascula-app 2>/dev/null || true

# Determina el puerto configurado y verifica disponibilidad
BASCULA_WEB_PORT=8080
if [[ -f "${DEFAULT_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${DEFAULT_FILE}"
fi
PORT_CHECK="${BASCULA_WEB_PORT:-8080}"
if ss -ltn | awk -v port=":${PORT_CHECK}$" 'NR>1 && $4 ~ port {exit 0} END {exit 1}'; then
  echo "[install-2] ERROR: puerto ${PORT_CHECK} en uso. Libera o ajusta BASCULA_WEB_PORT en /etc/default/bascula-web" >&2
  exit 1
fi

# Habilita y arranca los servicios ya con flags creados
systemctl enable bascula-web bascula-app
systemctl restart bascula-web
systemctl restart bascula-app

echo "[install-2-app] Servicios bascula-web y bascula-app activos"

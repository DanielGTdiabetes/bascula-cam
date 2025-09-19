#!/usr/bin/env bash
set -Eeuo pipefail

# Wrapper para ejecutar el instalador con SSH forzado y entorno preservado.
# Uso:
#   bash scripts/run-installer-ssh.sh [opciones_instalador]
#
# Variables opcionales:
#   BASCULA_USER            Usuario objetivo (por defecto: bascula)
#   BASCULA_REPO_SSH_URL    URL SSH del repo (por defecto: git@github.com:DanielGTdiabetes/bascula-cam.git)

REPO_SSH_URL="${BASCULA_REPO_SSH_URL:-git@github.com:DanielGTdiabetes/bascula-cam.git}"

log() { echo "=> $*"; }

# Localiza el instalador o lo descarga si no existe
find_installer() {
  if [[ -f "scripts/install-all.sh" ]]; then
    echo "scripts/install-all.sh"; return 0
  fi
  if [[ -f "install-all.sh" ]]; then
    echo "./install-all.sh"; return 0
  fi
  local tmp="/tmp/bascula-install-$$.sh"
  local url="https://raw.githubusercontent.com/DanielGTdiabetes/bascula-cam/HEAD/scripts/install-all.sh"
  log "Descargando instalador desde ${url} …"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$url" -o "$tmp"
  else
    wget -qO "$tmp" "$url"
  fi
  chmod +x "$tmp"
  echo "$tmp"
}

main() {
  local installer
  installer="$(find_installer)"
  log "Usando instalador: ${installer}"

  # Usa sudo si no somos root
  if [[ $(id -u) -ne 0 ]]; then
    log "Elevando privilegios (sudo -E) y forzando clon por SSH…"
    sudo -E env BASCULA_USE_SSH=1 BASCULA_REPO_SSH_URL="${REPO_SSH_URL}" bash "$installer" "$@"
  else
    env BASCULA_USE_SSH=1 BASCULA_REPO_SSH_URL="${REPO_SSH_URL}" bash "$installer" "$@"
  fi
}

main "$@"


#!/usr/bin/env bash
set -euo pipefail
# -------------------------------------------------------------
# SMART BÁSCULA CAM - setup.sh
# Crea venv (opcional), instala deps y activa systemd (usuario)
# Uso:
#   bash setup.sh [--no-venv] [--path <dir>] [--branch <rama>]
# Ejemplos:
#   bash setup.sh
#   bash setup.sh --no-venv
#   bash setup.sh --path /opt/bascula-cam --branch main
# -------------------------------------------------------------

REPO_URL_DEFAULT="https://github.com/DanielGTdiabetes/bascula-cam.git"
BRANCH="main"
INSTALL_DIR="$HOME/bascula-cam"
USE_VENV=1

# -------- Parse args --------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-venv) USE_VENV=0; shift;;
    --path) INSTALL_DIR="$2"; shift 2;;
    --branch) BRANCH="$2"; shift 2;;
    *) echo "Arg no reconocido: $1"; exit 1;;
  esac
done

echo "==> Instalando en: $INSTALL_DIR"
echo "==> Rama: $BRANCH"
echo "==> venv: $([[ $USE_VENV -eq 1 ]] && echo 'sí' || echo 'no')"

# -------- Paquetes del sistema mínimos --------
echo "==> Instalando paquetes del sistema (puede requerir sudo)..."
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y git python3 python3-venv python3-pip python3-tk
else
  echo "Aviso: no se detecta apt-get; salta instalación de paquetes."
fi

# -------- Obtener código --------
if [[ -d "$INSTALL_DIR/.git" ]]; then
  echo "==> Repo ya existente; actualizando..."
  git -C "$INSTALL_DIR" fetch --all --prune
  git -C "$INSTALL_DIR" checkout "$BRANCH"
  git -C "$INSTALL_DIR" pull --ff-only origin "$BRANCH"
else
  echo "==> Clonando repo..."
  mkdir -p "$INSTALL_DIR"
  git clone --branch "$BRANCH" "$REPO_URL_DEFAULT" "$INSTALL_DIR"
fi

# -------- venv opcional --------
if [[ $USE_VENV -eq 1 ]]; then
  echo "==> Creando/actualizando venv..."
  python3 -m venv "$INSTALL_DIR/venv"
  # shellcheck disable=SC1091
  source "$INSTALL_DIR/venv/bin/activate"
  pip install --upgrade pip
  if [[ -f "$INSTALL_DIR/requirements.txt" ]]; then
    pip install -r "$INSTALL_DIR/requirements.txt"
  fi
fi

# -------- Instalar servicio systemd (usuario) --------
echo "==> Instalando servicio systemd (usuario)..."
mkdir -p "$HOME/.config/systemd/user"
cp "$INSTALL_DIR/systemd/bascula-cam.service" "$HOME/.config/systemd/user/"
# service ejecutará scripts/run-bascula.sh, que ya exporta DISPLAY=:0

# Permitir servicios de usuario al arrancar
if command -v loginctl >/dev/null 2>&1; then
  sudo loginctl enable-linger "$USER"
else
  echo "Aviso: loginctl no encontrado; puede que debas habilitar lingering manualmente."
fi

systemctl --user daemon-reload
systemctl --user enable bascula-cam.service
systemctl --user restart bascula-cam.service || systemctl --user start bascula-cam.service

echo "==> Servicio activo. Logs:"
echo "    journalctl --user -u bascula-cam -f"
echo "==> Prueba manual:"
echo "    DISPLAY=:0 "$INSTALL_DIR/scripts/run-bascula.sh""
echo "==> Listo."

#!/usr/bin/env bash
set -euo pipefail

# --- Paths
APP_DIR=""
APP_CANDIDATES=(
  "$HOME/bascula-cam"
  "/opt/bascula/current"
  "$HOME/bascula-cam-main"
)
for candidate in "${APP_CANDIDATES[@]}"; do
  if [ -d "$candidate" ]; then
    APP_DIR="$candidate"
    break
  fi
done

if [ -z "$APP_DIR" ]; then
  echo "[safe_run] ERROR: Directorio de aplicación no encontrado" >&2
  exit 1
fi
cd "$APP_DIR"

LOG_DIR="/var/log/bascula"
if ! mkdir -p "$LOG_DIR" 2>/dev/null; then
  LOG_DIR="$HOME/.bascula/logs"
  mkdir -p "$LOG_DIR" 2>/dev/null || true
fi

LOG="$LOG_DIR/app.log"
if ! touch "$LOG" 2>/dev/null; then
  LOG="$HOME/app.log"
  if ! touch "$LOG" 2>/dev/null; then
    LOG="/tmp/bascula-app.log"
    touch "$LOG" 2>/dev/null || true
  fi
fi

echo "[safe_run] Directorio de la app: $APP_DIR" | tee -a "$LOG"
echo "[safe_run] Registro en: $LOG" | tee -a "$LOG"

# --- Entorno Xorg mejorado
export DISPLAY=${DISPLAY:-:0}
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
export LC_ALL=C.UTF-8
export LANG=C.UTF-8

# Variables adicionales para Tkinter en kiosk
export XAUTHORITY=${XAUTHORITY:-$HOME/.Xauthority}
export XDG_SESSION_TYPE=${XDG_SESSION_TYPE:-x11}

# Verificar que X11 esté funcionando
echo "[safe_run] Verificando display $DISPLAY..." | tee -a "$LOG"
if ! xset q >/dev/null 2>&1; then
  echo "[safe_run] ERROR: No se puede conectar al display $DISPLAY" | tee -a "$LOG"
  echo "[safe_run] Intentando iniciar X11..." | tee -a "$LOG"
  # Intentar diferentes displays
  for disp in :0 :1; do
    export DISPLAY=$disp
    if xset q >/dev/null 2>&1; then
      echo "[safe_run] Display $disp funcionando" | tee -a "$LOG"
      break
    fi
  done
fi

# --- Recovery flag
REC_FLAG="/var/lib/bascula-updater/force_recovery"
if [ -f "$REC_FLAG" ]; then
  echo "[safe_run] Recovery flag encontrado, lanzando Recovery UI" | tee -a "$LOG"
  if [ -x ".venv/bin/python" ]; then
    exec .venv/bin/python -m bascula.ui.recovery_ui 2>>"$LOG"
  else
    exec python3 -m bascula.ui.recovery_ui 2>>"$LOG"
  fi
fi

# --- Venv opcional
PY=".venv/bin/python"
if [ -x "$PY" ]; then
  echo "[safe_run] Usando venv local" | tee -a "$LOG"
else
  PY="python3"
fi

# --- Configuración de pantalla para kiosk
echo "[safe_run] Configurando pantalla para kiosk..." | tee -a "$LOG"

# Desactivar ahorro de energía y protector de pantalla
if which xset >/dev/null 2>&1; then
  xset s off          # Desactivar screensaver
  xset -dpms          # Desactivar power management
  xset s noblank      # No blanquear pantalla
  echo "[safe_run] Configuración xset aplicada" | tee -a "$LOG"
fi

# Ocultar cursor del mouse
if which unclutter >/dev/null 2>&1; then
  unclutter -idle 0.1 -root &
  echo "[safe_run] Cursor oculto con unclutter" | tee -a "$LOG"
fi

# Configurar resolución si es necesario
if which xrandr >/dev/null 2>&1; then
  # Intentar configurar resolución óptima
  xrandr --output HDMI-1 --mode 1024x600 2>/dev/null || true
  echo "[safe_run] Configuración xrandr aplicada" | tee -a "$LOG"
fi

# --- Lanzar app con reintentos
echo "[safe_run] Lanzando app..." | tee -a "$LOG"

# Función para lanzar la app con reintentos
launch_app() {
  local attempt=1
  local max_attempts=3
  
  while [ $attempt -le $max_attempts ]; do
    echo "[safe_run] Intento $attempt de $max_attempts" | tee -a "$LOG"
    
    # Verificar display antes de cada intento
    if ! xset q >/dev/null 2>&1; then
      echo "[safe_run] Display no disponible en intento $attempt" | tee -a "$LOG"
      sleep 2
      attempt=$((attempt + 1))
      continue
    fi
    
    # Lanzar aplicación
    "$PY" main.py >>"$LOG" 2>&1
    exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
      echo "[safe_run] App terminó normalmente" | tee -a "$LOG"
      exit 0
    elif [ $exit_code -eq 1 ]; then
      echo "[safe_run] Error de importación o display, reintentando..." | tee -a "$LOG"
      sleep 3
    else
      echo "[safe_run] Error crítico (código $exit_code), terminando" | tee -a "$LOG"
      exit $exit_code
    fi
    
    attempt=$((attempt + 1))
  done
  
  echo "[safe_run] Máximo de intentos alcanzado, terminando" | tee -a "$LOG"
  exit 1
}

# Ejecutar función de lanzamiento
launch_app

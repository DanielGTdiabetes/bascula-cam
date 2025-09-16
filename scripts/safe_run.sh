#!/usr/bin/env bash
set -euo pipefail

# --- Debug info
echo "[safe_run] Starting with UID: $(id -u), GID: $(id -g)" >&2
echo "[safe_run] Current directory: $(pwd)" >&2
echo "[safe_run] Environment:" >&2
env | sort >&2

# --- Paths
APP_DIR=""
APP_CANDIDATES=(
  "/home/pi/bascula-cam"  # Primary location
  "$HOME/bascula-cam"
  "/opt/bascula/current"
  "$HOME/bascula-cam-main"
)

for candidate in "${APP_CANDIDATES[@]}"; do
  if [ -d "$candidate" ]; then
    APP_DIR="$candidate"
    echo "[safe_run] Found app directory: $APP_DIR" >&2
    break
  else
    echo "[safe_run] Directory not found: $candidate" >&2
  fi
done

if [ -z "$APP_DIR" ]; then
  echo "[safe_run] ERROR: Application directory not found in any of: ${APP_CANDIDATES[*]}" >&2
  exit 1
fi

# Ensure we can access the directory
if [ ! -r "$APP_DIR" ] || [ ! -x "$APP_DIR" ]; then
  echo "[safe_run] ERROR: Cannot access directory $APP_DIR (permission denied)" >&2
  ls -ld "$APP_DIR" >&2
  exit 1
fi

cd "$APP_DIR" || {
  echo "[safe_run] ERROR: Failed to change to directory: $APP_DIR" >&2
  exit 1
}

echo "[safe_run] Changed to directory: $(pwd)" >&2

# Create log directory with proper permissions
LOG_DIR="$HOME/.bascula/logs"
mkdir -p "$LOG_DIR" 2>/dev/null || {
  echo "[safe_run] WARNING: Failed to create log directory: $LOG_DIR" >&2
  LOG_DIR="/tmp/bascula-logs"
  mkdir -p "$LOG_DIR" 2>/dev/null || {
    echo "[safe_run] ERROR: Cannot create any log directory" >&2
    exit 1
  }
}

# Ensure the log directory is writable
if [ ! -w "$LOG_DIR" ]; then
  echo "[safe_run] WARNING: Log directory is not writable: $LOG_DIR" >&2
  LOG_DIR="/tmp/bascula-logs"
  mkdir -p "$LOG_DIR" && chmod 777 "$LOG_DIR" || {
    echo "[safe_run] ERROR: Cannot write to any log directory" >&2
    exit 1
  }
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

# --- Verificar modo headless
if [ "${BASCULA_HEADLESS:-}" = "1" ]; then
  echo "[safe_run] Modo headless activado, omitiendo configuración X11" | tee -a "$LOG"
  HEADLESS_MODE=true
else
  HEADLESS_MODE=false
  # --- Verificar y configurar display
  echo "[safe_run] Verificando display ${DISPLAY:-:0}..." | tee -a "$LOG"
  
  # Asegurar que DISPLAY esté configurado
  if [ -z "${DISPLAY:-}" ]; then
    export DISPLAY=":0"
    echo "[safe_run] DISPLAY no configurado, usando :0" | tee -a "$LOG"
  fi
  
  # Verificar acceso X11
  if ! xset -q >/dev/null 2>&1; then
    echo "[safe_run] ERROR: No se puede conectar al display ${DISPLAY}" | tee -a "$LOG"
    
    # Intentar diferentes displays
    for disp in :0 :1; do
      export DISPLAY="$disp"
      echo "[safe_run] Probando display $disp" | tee -a "$LOG"
      
      # Esperar hasta 10 segundos para que X11 esté disponible
      for i in {1..10}; do
        if xset -q >/dev/null 2>&1; then
          echo "[safe_run] Display $disp funcionando después de ${i}s" | tee -a "$LOG"
          break 2
        fi
        sleep 1
      done
    done
    
    # Verificación final
    if ! xset -q >/dev/null 2>&1; then
      echo "[safe_run] ERROR: No se pudo establecer conexión X11" | tee -a "$LOG"
      echo "[safe_run] Activando modo headless automáticamente" | tee -a "$LOG"
      HEADLESS_MODE=true
    fi
  else
    echo "[safe_run] Display ${DISPLAY} funcionando" | tee -a "$LOG"
  fi
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

# --- Configuración de pantalla (solo si no es headless)
if [ "$HEADLESS_MODE" = "false" ]; then
  echo "[safe_run] Configurando pantalla para kiosk..." | tee -a "$LOG"
  
  # Desactivar ahorro de energía y protector de pantalla
  if which xset >/dev/null 2>&1 && xset -q >/dev/null 2>&1; then
    xset s off 2>/dev/null || true          # Desactivar screensaver
    xset -dpms 2>/dev/null || true          # Desactivar power management
    xset s noblank 2>/dev/null || true      # No blanquear pantalla
    echo "[safe_run] Configuración xset aplicada" | tee -a "$LOG"
  else
    echo "[safe_run] xset no disponible o sin acceso X11" | tee -a "$LOG"
  fi
  
  # Ocultar cursor del mouse
  if which unclutter >/dev/null 2>&1; then
    unclutter -idle 0.1 -root &
    echo "[safe_run] Cursor oculto con unclutter" | tee -a "$LOG"
  fi
  
  # Configurar resolución si es necesario
  if which xrandr >/dev/null 2>&1 && xset -q >/dev/null 2>&1; then
    # Intentar configurar resolución óptima
    xrandr --output HDMI-1 --mode 1024x600 2>/dev/null || true
    echo "[safe_run] Configuración xrandr aplicada" | tee -a "$LOG"
  else
    echo "[safe_run] xrandr no disponible o sin acceso X11" | tee -a "$LOG"
  fi
else
  echo "[safe_run] Modo headless: omitiendo configuración de pantalla" | tee -a "$LOG"
fi

# --- Lanzar app con reintentos
echo "[safe_run] Lanzando app..." | tee -a "$LOG"

# Función para lanzar la app con reintentos
launch_app() {
  local attempt=1
  local max_attempts=3
  
  while [ $attempt -le $max_attempts ]; do
    echo "[safe_run] Intento $attempt de $max_attempts" | tee -a "$LOG"
    
    # Verificar display antes de cada intento (solo si no es headless)
    if [ "$HEADLESS_MODE" = "false" ] && ! xset q >/dev/null 2>&1; then
      echo "[safe_run] Display no disponible en intento $attempt" | tee -a "$LOG"
      sleep 2
      attempt=$((attempt + 1))
      continue
    fi
    
    # Lanzar aplicación
    if [ "$HEADLESS_MODE" = "true" ]; then
      echo "[safe_run] Iniciando en modo headless" | tee -a "$LOG"
      "$PY" -m bascula.services.headless_main >>"$LOG" 2>&1
    else
      echo "[safe_run] Iniciando interfaz gráfica" | tee -a "$LOG"
      "$PY" main.py >>"$LOG" 2>&1
    fi
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

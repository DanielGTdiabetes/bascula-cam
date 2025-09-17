#!/usr/bin/env bash
set -euo pipefail

# kiosk_start.sh - Script optimizado para iniciar la báscula en modo kiosk
# Este script maneja automáticamente los problemas comunes de display en Raspberry Pi

LOG_DIR="/var/log/bascula"
mkdir -p "$LOG_DIR" || true
LOG="$LOG_DIR/kiosk.log"

echo "$(date '+%Y-%m-%d %H:%M:%S') [kiosk_start] Iniciando configuración kiosk…" | tee -a "$LOG"

# --- Configuración de entorno ---
export DISPLAY=${DISPLAY:-:0}
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
export XAUTHORITY=${XAUTHORITY:-$HOME/.Xauthority}
export XDG_SESSION_TYPE=x11

# --- Esperar a que X11 esté disponible ---
wait_for_x11() {
    local timeout=30
    local count=0
    
    echo "[kiosk_start] Esperando X11…" | tee -a "$LOG"
    
    while [ $count -lt $timeout ]; do
        if xset q >/dev/null 2>&1; then
            echo "[kiosk_start] X11 disponible en $DISPLAY" | tee -a "$LOG"
            return 0
        fi
        
        echo "[kiosk_start] X11 no disponible, esperando… ($count/$timeout)" | tee -a "$LOG"
        sleep 1
        count=$((count + 1))
    done
    
    echo "[kiosk_start] ERROR: X11 no disponible después de ${timeout}s" | tee -a "$LOG"
    return 1
}

# --- Configurar kiosk mode ---
setup_kiosk() {
    echo "[kiosk_start] Configurando modo kiosk…" | tee -a "$LOG"
    
    # Desactivar protector de pantalla y ahorro de energía
    xset s off -dpms s noblank 2>/dev/null || true
    
    # Configurar resolución si es posible
    if command -v xrandr >/dev/null 2>&1; then
        # Detectar salidas disponibles
        OUTPUTS=$(xrandr --listmonitors 2>/dev/null | grep -o '[A-Z][A-Z]*-[0-9]*' || echo "HDMI-1")
        for output in $OUTPUTS; do
            # Intentar configurar resolución común para pantallas pequeñas
            xrandr --output "$output" --mode 1024x600 2>/dev/null || \
            xrandr --output "$output" --mode 1280x720 2>/dev/null || \
            xrandr --output "$output" --auto 2>/dev/null || true
        done
        echo "[kiosk_start] Configuración de resolución aplicada" | tee -a "$LOG"
    fi
    
    # Ocultar cursor
    if command -v unclutter >/dev/null 2>&1; then
        unclutter -idle 1 -root &
        echo "[kiosk_start] Cursor oculto" | tee -a "$LOG"
    fi
    
    # Configurar fondo negro
    if command -v xsetroot >/dev/null 2>&1; then
        xsetroot -solid black
        echo "[kiosk_start] Fondo negro configurado" | tee -a "$LOG"
    fi
}

# --- Función principal ---
main() {
    # Cambiar al directorio de la aplicación
    APP_DIR="/opt/bascula/current"
    [ -d "$APP_DIR" ] || APP_DIR="$HOME/bascula-cam-main"
    
    if [ ! -d "$APP_DIR" ]; then
        echo "[kiosk_start] ERROR: Directorio de aplicación no encontrado" | tee -a "$LOG"
        exit 1
    fi
    
    cd "$APP_DIR"
    echo "[kiosk_start] Directorio de trabajo: $(pwd)" | tee -a "$LOG"
    
    # Esperar X11
    if ! wait_for_x11; then
        echo "[kiosk_start] ERROR: No se pudo conectar a X11" | tee -a "$LOG"
        exit 1
    fi
    
    # Configurar kiosk
    setup_kiosk
    
    # Determinar Python a usar
    if [ -x ".venv/bin/python" ]; then
        PY=".venv/bin/python"
        echo "[kiosk_start] Usando Python del venv" | tee -a "$LOG"
    else
        PY="python3"
        echo "[kiosk_start] Usando Python del sistema" | tee -a "$LOG"
    fi
    
    # Ejecutar aplicación
    echo "[kiosk_start] Lanzando aplicación…" | tee -a "$LOG"
    exec "$PY" main.py 2>&1 | tee -a "$LOG"
}

# Ejecutar función principal
main "$@"

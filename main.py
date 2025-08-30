#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Báscula Digital Pro - Entrada principal
Aplicación de kiosko para báscula con ESP32 + HX711

Configuración via variables de entorno:
- BASCULA_SCALING: "auto" (recomendado)  
- BASCULA_BORDERLESS: "1" (kiosko)
- BASCULA_FULLSCREEN: "0" (evitar parpadeos)
- BASCULA_DEBUG: "1" (mostrar overlay debug)
"""

import sys
import os
import signal
import logging
from pathlib import Path

# Configurar logging básico
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Path.home() / "bascula_app.log")
    ]
)

logger = logging.getLogger("bascula")

def signal_handler(sig, frame):
    """Manejo limpio de señales del sistema."""
    logger.info(f"Señal recibida: {sig}")
    sys.exit(0)

def main():
    """Función principal."""
    try:
        # Registrar manejadores de señales
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        # Información del sistema
        logger.info("=== BÁSCULA DIGITAL PRO ===")
        logger.info(f"Python: {sys.version}")
        logger.info(f"Plataforma: {sys.platform}")
        logger.info(f"PID: {os.getpid()}")
        
        # Variables de entorno importantes
        env_vars = [
            "DISPLAY", "BASCULA_SCALING", "BASCULA_BORDERLESS", 
            "BASCULA_FULLSCREEN", "BASCULA_DEBUG", "PYTHONPATH"
        ]
        for var in env_vars:
            value = os.environ.get(var, "No configurada")
            logger.info(f"ENV {var}: {value}")
        
        # Verificar que estamos en el directorio correcto
        app_dir = Path(__file__).parent.absolute()
        os.chdir(app_dir)
        logger.info(f"Directorio de trabajo: {app_dir}")
        
        # Añadir al path para imports
        if str(app_dir) not in sys.path:
            sys.path.insert(0, str(app_dir))
        
        # Importar y ejecutar la aplicación
        logger.info("Inicializando interfaz gráfica...")
        from bascula.ui.app import BasculaAppTk
        
        # Crear y ejecutar aplicación
        app = BasculaAppTk()
        logger.info("Aplicación creada, iniciando bucle principal...")
        app.run()
        
    except KeyboardInterrupt:
        logger.info("Interrupción por teclado (Ctrl+C)")
        
    except ImportError as e:
        logger.error(f"Error de importación: {e}")
        logger.error("Verifica que todas las dependencias están instaladas")
        sys.exit(1)
        
    except Exception as e:
        logger.exception(f"Error inesperado: {e}")
        sys.exit(1)
        
    finally:
        logger.info("Aplicación finalizada")

if __name__ == "__main__":
    main()

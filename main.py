#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py (Versión Final Simplificada)
-------------------------------------
Punto de entrada principal de la aplicación.
Importa y ejecuta directamente la clase principal desde app.py.
"""
import logging
import sys
import os

# Configuración del logging para ver mensajes y errores
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout) # Muestra los logs en la consola
    ]
)

def main():
    """Función principal para lanzar la báscula."""
    logging.info("===========================")
    logging.info("=== BÁSCULA DIGITAL PRO ===")
    logging.info("===========================")
    logging.info("Python: %s", sys.version)
    logging.info("Plataforma: %s", sys.platform)
    logging.info("DISPLAY: %s", os.environ.get("DISPLAY", "No definido"))

    try:
        # --- ¡CAMBIO CLAVE! ---
        # Importamos directamente la clase de la aplicación desde app.py
        # Esto es más robusto y menos propenso a errores.
        from app import BasculaAppTk
        
        logging.info("Clase de la aplicación 'BasculaAppTk' cargada correctamente desde app.py.")
        
        # Creamos una instancia y la ejecutamos
        app = BasculaAppTk()
        app.run()

    except ImportError:
        logging.error("Error Crítico: No se pudo encontrar el archivo 'app.py' o la clase 'BasculaAppTk'.")
        logging.error("Asegúrate de que 'app.py' está en el mismo directorio que 'main.py'.")
        sys.exit(1)
    except Exception as e:
        logging.error("Error inesperado al arrancar la aplicación: %s", e, exc_info=True)
        sys.exit(1)
    finally:
        logging.info("Aplicación finalizada.")

if __name__ == "__main__":
    main()

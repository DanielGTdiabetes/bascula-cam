#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py (Versión Definitiva y Completa)
---------------------------------------
Punto de entrada que importa y ejecuta la aplicación principal.
"""
import logging
import sys
import os

# Configuración del logging para ver mensajes de estado y errores en la consola
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

def main():
    """Función principal para lanzar la báscula."""
    logging.info("===========================")
    logging.info("=== BÁSCULA DIGITAL PRO ===")
    logging.info("===========================")

    try:
        # Importamos directamente la clase de la aplicación desde app.py
        from app import BasculaAppTk
        logging.info("Clase 'BasculaAppTk' cargada correctamente desde app.py.")
        
        # Creamos una instancia y la ejecutamos
        app = BasculaAppTk()
        app.run()

    except ImportError as e:
        logging.error("Error Crítico: No se pudo encontrar 'app.py' o la clase 'BasculaAppTk'. %s", e)
        sys.exit(1)
    except Exception as e:
        logging.error("Error fatal al arrancar la aplicación: %s", e, exc_info=True)
        sys.exit(1)
    finally:
        logging.info("Aplicación finalizada.")

if __name__ == "__main__":
    main()

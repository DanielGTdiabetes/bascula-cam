#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py (Versión Definitiva y Completa)
---------------------------------------
Punto de entrada que importa y ejecuta la aplicación principal.
"""
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

def main():
    logging.info("===========================")
    logging.info("=== BÁSCULA DIGITAL PRO ===")
    logging.info("===========================")
    try:
        from app import BasculaAppTk
        logging.info("Clase 'BasculaAppTk' cargada correctamente desde app.py.")
        app = BasculaAppTk()
        app.run()
    except ImportError as e:
        logging.error("Error: no se pudo importar 'BasculaAppTk' desde app.py: %s", e)
        sys.exit(1)
    except Exception as e:
        logging.error("Error fatal al arrancar: %s", e, exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

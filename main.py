#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
main.py - Punto de entrada principal
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
        # Importar desde la ubicación correcta
        from bascula.ui.app import BasculaAppTk
        logging.info("Clase 'BasculaAppTk' cargada correctamente.")
        app = BasculaAppTk()
        app.run()
    except ImportError as e:
        logging.error("Error: no se pudo importar 'BasculaAppTk': %s", e)
        sys.exit(1)
    except Exception as e:
        logging.error("Error fatal al arrancar: %s", e, exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

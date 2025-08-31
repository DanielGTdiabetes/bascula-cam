#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Entry point de la aplicación.
Acepta tanto BasculaApp como el alias de compatibilidad BasculaAppTk.
"""
import logging
import sys
import os
from bascula.ui.app import BasculaApp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - bascula - %(levelname)s - %(message)s",
)

def main():
    logging.info("=== BÁSCULA DIGITAL PRO ===")
    logging.info("Python: %s", sys.version)
    logging.info("Plataforma: %s", sys.platform)
    logging.info("ENV DISPLAY: %s", os.environ.get("DISPLAY", "No definido"))
    logging.info("ENV PYTHONPATH: %s", os.environ.get("PYTHONPATH", "No definido"))

    logging.info("Inicializando interfaz gráfica...")
    try:
        app = BasculaApp()
        logging.info("Aplicación creada, iniciando bucle principal...")
        if hasattr(app, "run"):
            app.run()
        else:
            app.mainloop()
    except Exception as e:
        logging.error("Error inesperado: %s", e, exc_info=True)
    finally:
        logging.info("Aplicación finalizada")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Entry point de la aplicación.
No impone UI: intenta usar tu BasculaApp (o BasculaAppTk) donde la tengas.
"""
import logging
import sys
import os
import importlib

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - bascula - %(levelname)s - %(message)s",
)

CANDIDATES = [
    # Rutas habituales
    ("bascula.ui.app", "BasculaApp"),
    ("bascula.ui.app", "BasculaAppTk"),
    ("bascula.app", "BasculaApp"),
    ("bascula.app", "BasculaAppTk"),
    # Proyectos que usan un único módulo de UI:
    ("app", "BasculaApp"),
    ("app", "BasculaAppTk"),
    ("screen", "BasculaApp"),
    ("screen", "BasculaAppTk"),
]

def load_app_class():
    errors = []
    for module_name, class_name in CANDIDATES:
        try:
            mod = importlib.import_module(module_name)
            if hasattr(mod, class_name):
                return getattr(mod, class_name), f"{module_name}.{class_name}"
        except Exception as e:
            errors.append(f"{module_name}: {e!s}")
    raise ImportError("No se encontró la clase de aplicación en rutas conocidas. Intentos: " + " | ".join(errors))

def main():
    logging.info("=== BÁSCULA DIGITAL PRO ===")
    logging.info("Python: %s", sys.version)
    logging.info("Plataforma: %s", sys.platform)
    logging.info("ENV DISPLAY: %s", os.environ.get("DISPLAY", "No definido"))
    logging.info("ENV PYTHONPATH: %s", os.environ.get("PYTHONPATH", "No definido"))

    try:
        AppClass, where = load_app_class()
        logging.info("UI detectada: %s", where)
        app = AppClass()
        logging.info("Aplicación creada, iniciando bucle principal...")
        if hasattr(app, "run"):
            app.run()
        else:
            app.mainloop()
    except Exception as e:
        logging.error("Error inesperado al arrancar la app: %s", e, exc_info=True)
    finally:
        logging.info("Aplicación finalizada")

if __name__ == "__main__":
    main()

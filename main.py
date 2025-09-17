#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Punto de entrada principal para la interfaz de Báscula Cam."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Asegurar que la raíz del repositorio esté en sys.path
REPO_ROOT = Path(__file__).parent.absolute()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Configuración básica de logging a stdout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("bascula.main")


def main() -> int:
    """Ejecuta la aplicación BasculaApp."""
    logger.info("=== BÁSCULA DIGITAL PRO - INICIO ===")

    try:
        if sys.platform != "win32" and not os.environ.get("DISPLAY"):
            logger.error("Entorno sin servidor gráfico (DISPLAY). No se puede iniciar la UI.")
            return 1

        from bascula.ui.app import BasculaApp

        logger.info("Inicializando BasculaApp...")
        app = BasculaApp()
        logger.info("Aplicación inicializada. Iniciando loop principal de Tkinter.")
        app.run()
        logger.info("Loop principal finalizado correctamente.")
        return 0

    except ImportError as exc:
        logger.error("No se pudo importar BasculaApp u otros módulos requeridos: %s", exc)
        logger.debug("Detalles de ImportError", exc_info=True)
        return 1

    except KeyboardInterrupt:
        logger.info("Ejecución interrumpida por el usuario.")
        return 0

    except Exception as exc:  # pylint: disable=broad-except
        logger.error("Error inesperado en la aplicación: %s", exc, exc_info=True)
        return 2

    finally:
        logger.info("=== BÁSCULA DIGITAL PRO - FIN ===")


if __name__ == "__main__":
    sys.exit(main())

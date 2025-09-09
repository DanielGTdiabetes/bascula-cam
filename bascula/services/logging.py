"""
bascula/services/logging.py

Módulo centralizado de logging para la Báscula Digital Pro.
Versión robusta que maneja errores de permisos.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys
import os

# Directorio de logs con fallback
try:
    LOG_DIR = Path.home() / ".bascula" / "logs"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE = LOG_DIR / "bascula.log"
except PermissionError:
    # Fallback a /tmp si no tenemos permisos en home
    LOG_DIR = Path("/tmp") / "bascula_logs"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE = LOG_DIR / "bascula.log"
    print(f"Advertencia: Usando directorio temporal para logs: {LOG_DIR}")
except Exception as e:
    # Último recurso: logs solo en consola
    LOG_DIR = None
    LOG_FILE = None
    print(f"Advertencia: No se pueden crear directorios de logs: {e}")


def setup_logging(level=logging.INFO):
    """
    Configura logging rotativo con manejo de errores.
    - Nivel por defecto: INFO
    - Tamaño máximo: 1 MB
    - Máx. 3 archivos rotados
    """
    logger = logging.getLogger("bascula")
    logger.setLevel(level)

    # Evita añadir handlers duplicados si se llama varias veces
    if logger.handlers:
        return logger

    # Formato de los mensajes
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Handler a fichero con rotación (si es posible)
    if LOG_FILE:
        try:
            file_handler = RotatingFileHandler(
                LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except (PermissionError, OSError) as e:
            print(f"Advertencia: No se puede escribir en archivo de log: {e}")

    # Handler a consola (stderr) — siempre disponible
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.info("Logging inicializado")
    return logger

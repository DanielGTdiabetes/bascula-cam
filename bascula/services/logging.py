"""
bascula/services/logging.py

Módulo centralizado de logging para la Báscula Digital Pro.
Crea un logger rotativo en ~/.bascula/logs/bascula.log
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

# Directorio de logs
LOG_DIR = Path.home() / ".bascula" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "bascula.log"


def setup_logging(level=logging.INFO):
    """
    Configura logging rotativo.
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

    # Handler a fichero con rotación
    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Handler a consola (stderr) — útil en pruebas
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    logger.info("Logging inicializado")
    return logger

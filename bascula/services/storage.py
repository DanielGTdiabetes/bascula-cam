"""
bascula/services/storage.py

Módulo de persistencia para la Báscula Digital Pro.
Encargado de leer/escribir configuraciones y datos en JSON y CSV.
"""

import os
import json
import csv
import logging
from datetime import datetime
from pathlib import Path

# Directorio base de almacenamiento (en $HOME/.bascula)
BASCULA_DIR = Path.home() / ".bascula"
DATA_DIR = BASCULA_DIR / "data"
LOG_DIR = BASCULA_DIR / "logs"

# Archivos por defecto
CONFIG_FILE = BASCULA_DIR / "config.json"
HISTORY_FILE = DATA_DIR / "history.csv"

# Aseguramos que las carpetas existen
for d in (BASCULA_DIR, DATA_DIR, LOG_DIR):
    d.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("bascula.storage")


# -------------------------------
# Funciones JSON
# -------------------------------

def save_json(data, path: Path):
    """
    Guarda un diccionario/estructura en un archivo JSON.
    """
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Guardado JSON en {path}")
    except Exception as e:
        logger.error(f"No se pudo guardar JSON en {path}: {e}")
        raise


def load_json(path: Path, default=None):
    """
    Carga un archivo JSON y lo devuelve como dict.
    Si no existe, devuelve `default`.
    """
    try:
        if not path.exists():
            logger.warning(f"No existe {path}, usando valor por defecto")
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"No se pudo leer JSON en {path}: {e}")
        return default


# -------------------------------
# Funciones CSV (historial de pesajes)
# -------------------------------

CSV_HEADERS = ["timestamp", "weight_g", "item", "meal_id"]


def append_csv(weight_g: float, item: str = "", meal_id: str = ""):
    """
    Añade una entrada al historial CSV.
    """
    is_new = not HISTORY_FILE.exists()
    try:
        with open(HISTORY_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
            if is_new:
                writer.writeheader()
            writer.writerow({
                "timestamp": datetime.now().isoformat(),
                "weight_g": weight_g,
                "item": item,
                "meal_id": meal_id,
            })
        logger.info(f"Añadido registro CSV: {weight_g} g, {item}, {meal_id}")
    except Exception as e:
        logger.error(f"No se pudo escribir en {HISTORY_FILE}: {e}")
        raise


def read_csv(limit: int = 100):
    """
    Devuelve las últimas `limit` entradas del historial CSV como lista de dicts.
    """
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
        return reader[-limit:]
    except Exception as e:
        logger.error(f"No se pudo leer {HISTORY_FILE}: {e}")
        return []


def clear_csv():
    """
    Borra el historial CSV.
    """
    try:
        if HISTORY_FILE.exists():
            HISTORY_FILE.unlink()
            logger.info(f"Historial CSV borrado: {HISTORY_FILE}")
    except Exception as e:
        logger.error(f"No se pudo borrar {HISTORY_FILE}: {e}")


# -------------------------------
# Configuración principal
# -------------------------------

DEFAULT_CONFIG = {
    "port": "/dev/serial0",
    "baud": 115200,
    "calib_factor": 1.0,
    "smoothing": 10,
    "decimals": 1,
    "no_emoji": False,
}

def load_config():
    """
    Carga la configuración principal desde config.json.
    Si no existe, crea una con DEFAULT_CONFIG.
    """
    if not CONFIG_FILE.exists():
        save_json(DEFAULT_CONFIG, CONFIG_FILE)
        return DEFAULT_CONFIG
    return load_json(CONFIG_FILE, default=DEFAULT_CONFIG)


def save_config(cfg: dict):
    """
    Guarda la configuración principal en config.json.
    """
    save_json(cfg, CONFIG_FILE)


# -------------------------------
# Utilidad
# -------------------------------

def ensure_paths():
    """
    Reasegura que todas las rutas necesarias existen.
    """
    for d in (BASCULA_DIR, DATA_DIR, LOG_DIR):
        d.mkdir(parents=True, exist_ok=True)
    return {
        "config": CONFIG_FILE,
        "history": HISTORY_FILE,
        "logs": LOG_DIR,
    }

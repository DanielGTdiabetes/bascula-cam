# utils.py - VERSIÓN RECOMENDADA PARA v2.1
import json, os
from collections import deque
from pathlib import Path

# --- CORRECCIÓN ---
# Prioriza la variable de entorno que define el instalador.
# Si no existe, usa la nueva ruta por defecto.
_CFG_ENV = os.environ.get('BASCULA_CFG_DIR', '').strip()
CONFIG_PATH = Path(_CFG_ENV) / "config.json" if _CFG_ENV else Path.home() / ".bascula" / "config.json"

DEFAULT_CONFIG = {
    "port": "/dev/serial0",
    "baud": 115200,
    "calib_factor": 1.0,
    # ... (el resto del diccionario DEFAULT_CONFIG se mantiene igual)
}

def load_config():
    try:
        # Asegurarse de que el directorio existe
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        cfg = DEFAULT_CONFIG.copy()
        cfg.update(data)
        # sanea
        cfg["smoothing"] = max(1, int(cfg.get("smoothing", 5)))
        cfg["decimals"] = max(0, int(cfg.get("decimals", 0)))
        return cfg
    except (FileNotFoundError, json.JSONDecodeError):
        # Si el archivo no existe o está corrupto, usa y guarda el por defecto
        save_config(DEFAULT_CONFIG.copy())
        return DEFAULT_CONFIG.copy()
    except Exception:
        return DEFAULT_CONFIG.copy()

def save_config(cfg: dict):
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = str(CONFIG_PATH) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
        os.replace(tmp, CONFIG_PATH)
    except Exception:
        # Aquí podrías añadir un log si la escritura falla
        pass

# ... (La clase MovingAverage se mantiene igual)

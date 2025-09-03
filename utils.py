# -*- coding: utf-8 -*-
import json, os
from collections import deque

CONFIG_PATH = os.path.expanduser("~/bascula-cam/config.json")

DEFAULT_CONFIG = {
    "port": "/dev/serial0",
    "baud": 115200,
    "calib_factor": 1.0,   # gramos por unidad bruta
    "unit": "g",           # "g" o "kg"
    "smoothing": 5,        # muestras media móvil
    "decimals": 0,         # 0 = sin decimales
    "diabetic_mode": False, # mostrar glucosa si hay Nightscout
    "sound_enabled": True,
    "sound_theme": "beep",   # 'beep' o 'voice_es'
    # Retención de comidas (meals.jsonl)
    "meals_max_days": 180,
    "meals_max_entries": 1000,
    "meals_max_bytes": 5_000_000,
    # Fotos
    "keep_photos": False,   # si False, borra staging al iniciar
    # Asesor experimental de bolo
    "advisor_enabled": False,
    # Parámetros bolo (mg/dL y g/U)
    "target_bg_mgdl": 110,
    "isf_mgdl_per_u": 50,
    "carb_ratio_g_per_u": 10,
    "dia_hours": 4
}

def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        cfg = DEFAULT_CONFIG.copy()
        cfg.update(data)
        # sanea
        cfg["smoothing"] = max(1, int(cfg.get("smoothing", 5)))
        cfg["decimals"] = max(0, int(cfg.get("decimals", 0)))
        return cfg
    except Exception:
        return DEFAULT_CONFIG.copy()

def save_config(cfg: dict):
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.replace(tmp, CONFIG_PATH)

class MovingAverage:
    def __init__(self, size=5):
        self.size = max(1, int(size))
        self.buf = deque(maxlen=self.size)

    def add(self, x):
        self.buf.append(float(x))
        return sum(self.buf)/len(self.buf) if self.buf else 0.0

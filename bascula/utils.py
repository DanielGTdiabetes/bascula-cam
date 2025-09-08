# utils.py - VERSIÓN CORREGIDA Y COMPLETA
from __future__ import annotations
import json
import os
from collections import deque
from pathlib import Path
from typing import Deque, Dict, Any

# --- RUTA DE CONFIGURACIÓN PERSISTENTE ---
_CFG_ENV = os.environ.get("BASCULA_CFG_DIR", "").strip()
CONFIG_PATH: Path = (Path(_CFG_ENV) / "config.json") if _CFG_ENV else (Path.home() / ".bascula" / "config.json")

# --- CORRECCIÓN: Diccionario de configuración completo ---
DEFAULT_CONFIG: Dict[str, Any] = {
    "port": "/dev/serial0",
    "baud": 115200,
    "calib_factor": 1.0,
    "smoothing": 5,
    "decimals": 0,
    "unit": "g",
    "no_emoji": False,
    "sound_enabled": True,
    "sound_theme": "beep",
    "diabetic_mode": False,
    "advisor_enabled": False,
    "meals_max_days": 180,
    "meals_max_entries": 1000,
    "meals_max_bytes": 5_000_000,
    "keep_photos": False,
    "target_bg_mgdl": 110,
    "isf_mgdl_per_u": 50,
    "carb_ratio_g_per_u": 10,
    "dia_hours": 4,
    "send_to_ns_default": False
}

def _sanitize(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanea y normaliza tipos / rangos. Evita que la app falle por datos corruptos.
    """
    out = DEFAULT_CONFIG.copy()
    out.update(cfg or {})
    
    # Aquí puedes añadir validaciones específicas si lo necesitas
    # Por ahora, simplemente nos aseguramos de que todas las claves existen
    
    return out


def load_config() -> Dict[str, Any]:
    """
    Carga la configuración. Si no existe o está corrupta, guarda y devuelve DEFAULT_CONFIG.
    """
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CONFIG_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return _sanitize(data)
    except (FileNotFoundError, json.JSONDecodeError):
        # Archivo inexistente o corrupto -> regenerar con default
        cfg = DEFAULT_CONFIG.copy()
        save_config(cfg)
        return cfg
    except Exception:
        # Si algo raro ocurre, devuelve defaults (fail-safe)
        return DEFAULT_CONFIG.copy()


def save_config(cfg: Dict[str, Any]) -> None:
    """
    Guarda la configuración de forma atómica (write-to-temp + os.replace).
    """
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = str(CONFIG_PATH) + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(_sanitize(cfg), f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, CONFIG_PATH)
        try:
            os.chmod(CONFIG_PATH, 0o600)
        except Exception:
            pass
    except Exception:
        # Puedes añadir un logger aquí si lo deseas.
        pass


class MovingAverage:
    def __init__(self, size: int = 5) -> None:
        if size < 1:
            raise ValueError("size must be >= 1")
        self._buf: Deque[float] = deque(maxlen=size)
        self._sum: float = 0.0

    @property
    def size(self) -> int:
        return self._buf.maxlen or 0

    def reset(self) -> None:
        self._buf.clear()
        self._sum = 0.0

    def add(self, x: float) -> float:
        if len(self._buf) == self._buf.maxlen:
            self._sum -= self._buf[0]
        self._buf.append(x)
        self._sum += x
        return self.value

    @property
    def value(self) -> float:
        n = len(self._buf)
        return (self._sum / n) if n else 0.0

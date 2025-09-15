# utils.py - VERSIÓN ROBUSTA CON MANEJO DE PERMISOS
from __future__ import annotations
import json
import os
from collections import deque
from pathlib import Path
from typing import Deque, Dict, Any
import tempfile

# --- RUTA DE CONFIGURACIÓN PERSISTENTE ---
_CFG_ENV = os.environ.get("BASCULA_CFG_DIR", "").strip()

# Intentar usar el directorio configurado o el home del usuario
try:
    if _CFG_ENV:
        CONFIG_PATH = Path(_CFG_ENV) / "config.json"
    else:
        config_dir = Path.home() / ".bascula"
        config_dir.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH = config_dir / "config.json"
except (PermissionError, OSError):
    # Fallback a directorio temporal
    CONFIG_PATH = Path(tempfile.gettempdir()) / "bascula_config.json"
    print(f"Advertencia: Usando configuración temporal en {CONFIG_PATH}")

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
    "auto_capture_enabled": True,
    "auto_capture_min_delta_g": 8,
    "stability_window_ms": 800,
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
    ,
    # Audio/voz
    "mic_device": "",
    "mic_rate": 16000,
    "mic_duration": 3,
    "asr_cmd": "hear.sh",
    "tts_cmd": "say.sh"
}

def _sanitize(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanea y normaliza tipos / rangos. Evita que la app falle por datos corruptos.
    """
    out = DEFAULT_CONFIG.copy()
    out.update(cfg or {})
    return out


def load_config() -> Dict[str, Any]:
    """
    Carga la configuración. Si no existe o está corrupta, guarda y devuelve DEFAULT_CONFIG.
    Con manejo de errores de permisos.
    """
    try:
        if CONFIG_PATH.exists():
            with CONFIG_PATH.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return _sanitize(data)
        else:
            # No existe, crear con defaults
            cfg = DEFAULT_CONFIG.copy()
            save_config(cfg)
            return cfg
    except (FileNotFoundError, json.JSONDecodeError, PermissionError, OSError) as e:
        print(f"Advertencia cargando configuración: {e}")
        # Devolver defaults sin guardar si hay problemas
        return DEFAULT_CONFIG.copy()


def save_config(cfg: Dict[str, Any]) -> None:
    """
    Guarda la configuración de forma atómica (write-to-temp + os.replace).
    Con manejo de errores de permisos.
    """
    try:
        # Asegurar que el directorio padre existe
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        
        # Escribir a archivo temporal primero
        tmp_path = str(CONFIG_PATH) + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(_sanitize(cfg), f, indent=2, ensure_ascii=False)
        
        # Reemplazar atómicamente
        os.replace(tmp_path, CONFIG_PATH)
        
        # Intentar ajustar permisos (puede fallar en algunos sistemas)
        try:
            os.chmod(CONFIG_PATH, 0o600)
        except:
            pass
            
    except (PermissionError, OSError) as e:
        print(f"Advertencia: No se pudo guardar configuración: {e}")
        # No lanzar excepción, la app puede continuar con config en memoria


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

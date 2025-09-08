# utils.py - VERSIÓN RECOMENDADA PARA v2.1 (persistencia + robustez)
# Integra con el instalador v2.1: respeta BASCULA_CFG_DIR y cae a ~/.bascula/config.json

from __future__ import annotations

import json
import os
from collections import deque
from pathlib import Path
from typing import Deque, Dict, Any, Optional


# ------------------------------------------------------------------------------
# RUTA DE CONFIGURACIÓN (persistente)
# - Primero intenta BASCULA_CFG_DIR (inyectado por systemd en v2.1)
# - Si no existe, usa ~/.bascula/config.json
# ------------------------------------------------------------------------------
_CFG_ENV = os.environ.get("BASCULA_CFG_DIR", "").strip()
CONFIG_PATH: Path = (Path(_CFG_ENV) / "config.json") if _CFG_ENV else (Path.home() / ".bascula" / "config.json")


# ------------------------------------------------------------------------------
# DEFAULT_CONFIG
# Mantén este bloque sincronizado con lo que realmente usa la app.
# (si la app necesita más claves, añádelas aquí para evitar KeyError)
# ------------------------------------------------------------------------------
DEFAULT_CONFIG: Dict[str, Any] = {
    "port": "/dev/serial0",
    "baud": 115200,
    "calib_factor": 1.0,   # multiplicador de calibración HX711
    "smoothing": 5,        # tamaño de ventana del filtro de media móvil
    "decimals": 0,         # decimales a mostrar en la UI
    "no_emoji": False,     # si True, desactiva emojis en la UI
    # Puedes añadir más opciones que uses en la app, por ejemplo:
    # "units": "g",
    # "sound_enabled": True,
    # "voice": "es",
}


def _sanitize(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanea y normaliza tipos / rangos. Evita reventar la app por datos corruptos.
    """
    out = DEFAULT_CONFIG.copy()
    out.update(cfg or {})

    # enteros/bounds
    try:
        out["smoothing"] = int(out.get("smoothing", DEFAULT_CONFIG["smoothing"]))
        if out["smoothing"] < 1:
            out["smoothing"] = 1
        if out["smoothing"] > 1000:
            out["smoothing"] = 1000
    except Exception:
        out["smoothing"] = DEFAULT_CONFIG["smoothing"]

    try:
        out["decimals"] = int(out.get("decimals", DEFAULT_CONFIG["decimals"]))
        if out["decimals"] < 0:
            out["decimals"] = 0
        if out["decimals"] > 6:
            out["decimals"] = 6
    except Exception:
        out["decimals"] = DEFAULT_CONFIG["decimals"]

    # floats
    try:
        out["calib_factor"] = float(out.get("calib_factor", DEFAULT_CONFIG["calib_factor"]))
        if not (-1e6 < out["calib_factor"] < 1e6):
            out["calib_factor"] = DEFAULT_CONFIG["calib_factor"]
    except Exception:
        out["calib_factor"] = DEFAULT_CONFIG["calib_factor"]

    # strings/bools
    try:
        out["port"] = str(out.get("port", DEFAULT_CONFIG["port"])).strip() or DEFAULT_CONFIG["port"]
    except Exception:
        out["port"] = DEFAULT_CONFIG["port"]

    out["baud"] = int(out.get("baud", DEFAULT_CONFIG["baud"])) if str(out.get("baud", "")).isdigit() else DEFAULT_CONFIG["baud"]
    out["no_emoji"] = bool(out.get("no_emoji", DEFAULT_CONFIG["no_emoji"]))

    return out


def load_config() -> Dict[str, Any]:
    """
    Carga la configuración. Si no existe o está corrupta, guarda y devuelve DEFAULT_CONFIG.
    Crea el directorio padre si no existe.
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
    Si falla, no lanza excepción (para no romper la app en UI); logéalo desde la app si lo necesitas.
    """
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = str(CONFIG_PATH) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_sanitize(cfg), f, indent=2, ensure_ascii=False)
        os.replace(tmp, CONFIG_PATH)
        try:
            # Endurecer permisos (600) si el FS lo permite
            os.chmod(CONFIG_PATH, 0o600)
        except Exception:
            pass
    except Exception:
        # Aquí podrías añadir un logger si lo deseas.
        pass


# ------------------------------------------------------------------------------
# Filtro de media móvil para estabilizar lecturas (ej. HX711)
# ------------------------------------------------------------------------------
class MovingAverage:
    """
    Filtro de media móvil con ventana deslizante.
    - add(x) añade una muestra y devuelve la media actual.
    - value devuelve la media (0.0 si está vacío).
    - reset vacía el buffer.
    """

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
        # Si está lleno, restamos el que va a salir antes de apendear
        if len(self._buf) == self._buf.maxlen:
            self._sum -= self._buf[0]
        self._buf.append(x)
        self._sum += x
        return self.value

    @property
    def value(self) -> float:
        n = len(self._buf)
        return (self._sum / n) if n else 0.0

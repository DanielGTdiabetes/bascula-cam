# -*- coding: utf-8 -*-
from __future__ import annotations
import json
import os
from dataclasses import dataclass, asdict, field
from typing import Any, Dict

# Ruta de configuración por defecto (~/.bascula/config.json)
def _default_config_path() -> str:
    home = os.path.expanduser("~")
    cfg_dir = os.path.join(home, ".bascula")
    os.makedirs(cfg_dir, exist_ok=True)
    return os.path.join(cfg_dir, "config.json")

@dataclass
class FiltersConfig:
    fast_alpha: float = 0.5          # 0.01 .. 0.95
    stable_alpha: float = 0.12       # 0.01 .. 0.95
    stability_window: int = 20       # >= 3
    stability_threshold: float = 2.0 # gramos
    zero_tracking: bool = True
    zero_epsilon: float = 0.8        # gramos
    stable_hold_time_s: float = 1.5
    stable_min_samples: int = 10

@dataclass
class HardwareConfig:
    # Pines BCM para HX711
    hx711_dout_pin: int = 27   # DOUT
    hx711_sck_pin: int = 17    # SCK
    # Calibración básica
    reference_unit: float = 1.0  # factor (raw -> gramos), ajustar tras calibración
    offset_raw: float = 0.0      # offset raw tras tara/calibración
    # Estricta: si True y no hay hardware, error; si False, arranca simulador
    strict_hardware: bool = False

@dataclass
class PathsConfig:
    log_dir: str = os.path.join(os.path.expanduser("~"), ".bascula")
    log_file: str = "bascula.log"

@dataclass
class AppConfig:
    filters: FiltersConfig = field(default_factory=FiltersConfig)
    hardware: HardwareConfig = field(default_factory=HardwareConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)

def _merge(old: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
    """Merge superficial + anidado para garantizar campos nuevos."""
    out = dict(defaults)
    for k, v in old.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(v, out[k])
        else:
            out[k] = v
    return out

def _to_dict(cfg: AppConfig) -> Dict[str, Any]:
    d = asdict(cfg)
    return d

def _from_dict(data: Dict[str, Any]) -> AppConfig:
    # Merge con defaults por si faltan campos
    defaults = _to_dict(AppConfig())
    merged = _merge(data, defaults)
    # Reconstruir dataclasses
    f = merged.get("filters", {})
    h = merged.get("hardware", {})
    p = merged.get("paths", {})
    filters = FiltersConfig(**f)
    hardware = HardwareConfig(**h)
    paths = PathsConfig(**p)
    return AppConfig(filters=filters, hardware=hardware, paths=paths)

def load_config(path: str = None) -> AppConfig:
    if path is None:
        path = _default_config_path()
    if not os.path.exists(path):
        cfg = AppConfig()
        save_config(cfg, path)
        return cfg
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cfg = _from_dict(data if isinstance(data, dict) else {})
    except Exception:
        # Si está corrupto, reescribimos con defaults pero conservando copia
        try:
            backup = path + ".bak"
            if os.path.exists(path):
                os.replace(path, backup)
        except Exception:
            pass
        cfg = AppConfig()
        save_config(cfg, path)
    # Ensure log dir exists
    os.makedirs(cfg.paths.log_dir, exist_ok=True)
    return cfg

def save_config(cfg: AppConfig, path: str = None) -> None:
    if path is None:
        path = _default_config_path()
    data = _to_dict(cfg)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
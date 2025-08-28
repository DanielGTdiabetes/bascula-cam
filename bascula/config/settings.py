# -*- coding: utf-8 -*-
from __future__ import annotations
import json
import os
from dataclasses import dataclass, asdict
from typing import Any, Dict

def _default_config_path() -> str:
    home = os.path.expanduser("~")
    cfg_dir = os.path.join(home, ".bascula")
    os.makedirs(cfg_dir, exist_ok=True)
    return os.path.join(cfg_dir, "config.json")

@dataclass
class FiltersConfig:
    fast_alpha: float = 0.55
    stable_alpha: float = 0.12
    stability_window: int = 24
    stability_threshold: float = 2.0
    zero_tracking: bool = True
    zero_epsilon: float = 0.8
    stable_hold_time_s: float = 1.2
    stable_min_samples: int = 10

@dataclass
class HardwareConfig:
    hx711_dout_pin: int = 27        # BCM
    hx711_sck_pin: int = 17         # BCM
    reference_unit: float = 1.0     # factor (raw->g)
    offset_raw: float = 0.0         # offset raw
    strict_hardware: bool = False   # si True sin HX711 -> error
    samples_per_read: int = 8       # promedio por lectura

@dataclass
class PathsConfig:
    log_dir: str = os.path.join(os.path.expanduser("~"), ".bascula")
    log_file: str = "bascula.log"

@dataclass
class AppConfig:
    filters: FiltersConfig = FiltersConfig()
    hardware: HardwareConfig = HardwareConfig()
    paths: PathsConfig = PathsConfig()

def _merge(old: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(defaults)
    for k, v in old.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(v, out[k])
        else:
            out[k] = v
    return out

def _to_dict(cfg: AppConfig) -> Dict[str, Any]:
    return asdict(cfg)

def _from_dict(data: Dict[str, Any]) -> AppConfig:
    defaults = _to_dict(AppConfig())
    merged = _merge(data if isinstance(data, dict) else {}, defaults)
    f = FiltersConfig(**merged.get("filters", {}))
    h = HardwareConfig(**merged.get("hardware", {}))
    p = PathsConfig(**merged.get("paths", {}))
    return AppConfig(filters=f, hardware=h, paths=p)

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
        cfg = _from_dict(data)
    except Exception:
        try:
            if os.path.exists(path):
                os.replace(path, path + ".bak")
        except Exception:
            pass
        cfg = AppConfig()
        save_config(cfg, path)
    os.makedirs(cfg.paths.log_dir, exist_ok=True)
    return cfg

def save_config(cfg: AppConfig, path: str = None) -> None:
    if path is None:
        path = _default_config_path()
    data = _to_dict(cfg)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

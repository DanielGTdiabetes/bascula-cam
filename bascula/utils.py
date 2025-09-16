# -*- coding: utf-8 -*-
import json, os, pathlib
from collections import deque

CONFIG_DIR = pathlib.Path(os.environ.get("BASCULA_CFG_DIR", str(pathlib.Path.home() / ".config" / "bascula")))
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    # UI/tema
    "focus_mode": False,
    "theme_scanlines": False,
    "theme_glow": False,
    "textfx_enabled": True,
    # Audio/TTS
    "sound_enabled": True,
    "sound_theme": "beep",
    "piper_enabled": False,
    "piper_model": "",
    # Mascota / LLM
    "llm_api_key": "",
    "mascot_persona": "discreto",
    "mascot_max_per_hour": 3,
    "mascot_dnd": False,
    "mascot_llm_enabled": False,
    "mascot_llm_send_health": False,
    # Báscula
    "smoothing": 5,
    "decimals": 0,
    "unit": "g",
    "auto_capture_enabled": True,
    "auto_capture_min_delta_g": 8,
    "stability_window_ms": 800,
    "calib_factor": 1.0,
    # Glucemia/diabetes
    "diabetic_mode": False,
    "target_bg_mgdl": 110,
    "isf_mgdl_per_u": 50,
    "carb_ratio_g_per_u": 10,
    "dia_hours": 4,
    "bg_low_mgdl": 70,
    "bg_high_mgdl": 180,
    "bg_poll_s": 60,
    "bg_low_cooldown_min": 10,
    "bg_high_cooldown_min": 10,
    # Nightscout / datos
    "send_to_ns_default": False,
    "meals_max_days": 180,
    "meals_max_entries": 1000,
    "meals_max_bytes": 5000000,
    "keep_photos": False,
    # HW/puertos
    "port": "/dev/serial0",
    "baud": 115200,
    # Cámara / visión
    "vision_autosuggest_enabled": False,
    "vision_confidence_threshold": 0.85,
    "vision_min_weight_g": 20,
    "foodshot_size": "4608x2592",
}

def load_config() -> dict:
    try:
        if CONFIG_FILE.exists():
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            cfg = dict(DEFAULT_CONFIG)
            cfg.update(data or {})
            return cfg
    except Exception:
        pass
    return dict(DEFAULT_CONFIG)

def save_config(cfg: dict) -> None:
    try:
        CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


class MovingAverage:
    def __init__(self, size: int = 5) -> None:
        if size < 1:
            raise ValueError("size must be >= 1")
        self._buf = deque(maxlen=size)
        self._sum = 0.0

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

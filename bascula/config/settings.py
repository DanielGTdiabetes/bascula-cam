from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".bascula"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class UIFeatureFlags:
    tech_pin: int = 2468  # PIN técnico por defecto
    title: str = "⚖️ SMART BÁSCULA CAM"
    button_size: str = "xl"  # "md" | "lg" | "xl"
    keyboard_big: bool = True


@dataclass
class FilterSettings:
    stability_window: int = 8
    stability_threshold: float = 0.10
    fast_alpha: float = 0.45
    stable_alpha: float = 0.18


@dataclass
class CalibrationSettings:
    base_offset: Optional[float] = None
    scale_factor: Optional[float] = None
    last_ref_weight_g: Optional[float] = None


@dataclass
class AppSettings:
    ui: UIFeatureFlags = field(default_factory=UIFeatureFlags)
    filters: FilterSettings = field(default_factory=FilterSettings)
    calibration: CalibrationSettings = field(default_factory=CalibrationSettings)

    @classmethod
    def load(cls) -> "AppSettings":
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                ui = UIFeatureFlags(**data.get("ui", {}))
                filters = FilterSettings(**data.get("filters", {}))
                calibration = CalibrationSettings(**data.get("calibration", {}))
                return cls(ui=ui, filters=filters, calibration=calibration)
            except Exception:
                pass
        s = cls()
        s.save()
        return s

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

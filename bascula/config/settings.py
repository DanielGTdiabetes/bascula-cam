from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional
import json

# --- Defaults ---
DEFAULT_BASE_DIR = Path("~/bascula-cam").expanduser()
DEFAULT_OFFSET = 0.0
DEFAULT_SCALE = 1000.0

# ---------------- Calibration ----------------
@dataclass
class CalibrationConfig:
    base_offset: float = DEFAULT_OFFSET
    scale_factor: float = DEFAULT_SCALE
    # Compatibilidad con JSON antiguos
    last_ref_weight_g: Optional[float] = None
    last_ref_timestamp: Optional[str] = None

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "CalibrationConfig":
        return CalibrationConfig(
            base_offset=float(data.get("base_offset", DEFAULT_OFFSET)),
            scale_factor=float(data.get("scale_factor", DEFAULT_SCALE)),
            last_ref_weight_g=(
                float(data["last_ref_weight_g"])
                if "last_ref_weight_g" in data and data["last_ref_weight_g"] is not None
                else None
            ),
            last_ref_timestamp=data.get("last_ref_timestamp"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "base_offset": float(self.base_offset),
            "scale_factor": float(self.scale_factor),
            "last_ref_weight_g": self.last_ref_weight_g,
            "last_ref_timestamp": self.last_ref_timestamp,
        }

# ---------------- Filters (para ScaleService/ProfessionalWeightFilter) ----------------
@dataclass
class FiltersConfig:
    # Valores razonables (compatibles con el filtro “profesional”)
    stability_window: int = 10
    stability_threshold: float = 0.05
    filter_alpha: float = 0.15
    zero_threshold: float = 0.5
    # Extras por compatibilidad con otros filtros/variantes
    median_window: int = 7
    display_resolution: float = 0.1

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "FiltersConfig":
        # Acepta claves de distintas variantes sin romperse
        return FiltersConfig(
            stability_window=int(data.get("stability_window", 10)),
            stability_threshold=float(data.get("stability_threshold", 0.05)),
            filter_alpha=float(data.get("filter_alpha", 0.15)),
            zero_threshold=float(data.get("zero_threshold", 0.5)),
            median_window=int(data.get("median_window", 7)),
            display_resolution=float(data.get("display_resolution", 0.1)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stability_window": int(self.stability_window),
            "stability_threshold": float(self.stability_threshold),
            "filter_alpha": float(self.filter_alpha),
            "zero_threshold": float(self.zero_threshold),
            "median_window": int(self.median_window),
            "display_resolution": float(self.display_resolution),
        }

# ---------------- AppConfig ----------------
@dataclass
class AppConfig:
    base_dir: Path = DEFAULT_BASE_DIR
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    filters: FiltersConfig = field(default_factory=FiltersConfig)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "AppConfig":
        base_dir = Path(data.get("base_dir", str(DEFAULT_BASE_DIR))).expanduser()

        # Calibration: acepta bloque anidado y/o claves planas
        cal_block = data.get("calibration") or {}
        if "base_offset" in data or "scale_factor" in data:
            cal_block = {**cal_block}
            if "base_offset" in data:
                cal_block["base_offset"] = data["base_offset"]
            if "scale_factor" in data:
                cal_block["scale_factor"] = data["scale_factor"]
        calibration = CalibrationConfig.from_dict(cal_block)

        # Filters: si no existe bloque, usa defaults
        filt_block = data.get("filters") or {}
        filters = FiltersConfig.from_dict(filt_block)

        return AppConfig(base_dir=base_dir, calibration=calibration, filters=filters)

    def to_dict(self) -> Dict[str, Any]:
        # Guardamos anidado y espejo plano (compatibilidad)
        return {
            "base_dir": str(self.base_dir),
            "calibration": self.calibration.to_dict(),
            "filters": self.filters.to_dict(),
            "base_offset": float(self.calibration.base_offset),
            "scale_factor": float(self.calibration.scale_factor),
        }

    @classmethod
    def load(cls, filepath: Path) -> "AppConfig":
        if not filepath.exists():
            return cls.default()
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls.from_dict(data)
        except Exception:
            return cls.default()

    def save(self, filepath: Path) -> None:
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def default(cls) -> "AppConfig":
        return AppConfig()

# ---------------- API pública ----------------
def load_config() -> AppConfig:
    path = Path("~/.bascula/config.json").expanduser()
    return AppConfig.load(path)

def save_config(cfg: AppConfig) -> None:
    path = Path("~/.bascula/config.json").expanduser()
    cfg.save(path)

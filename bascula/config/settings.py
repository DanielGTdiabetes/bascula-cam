import os, json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Tuple

CONFIG_PATH = Path("~/.bascula/config.json").expanduser()

@dataclass
class HardwareConfig:
    hx711_dout_pin: int = 5
    hx711_sck_pin: int = 6
    hx711_gain: int = 64
    camera_resolution: Tuple[int, int] = (1640, 1232)

@dataclass
class FilterConfig:
    iir_alpha: float = 0.12
    median_window: int = 7
    stability_window: int = 12
    zero_band: float = 0.2
    display_resolution: float = 0.1
    auto_zero_rate: float = 0.35
    stability_threshold: float = 0.15

@dataclass
class UIConfig:
    fullscreen: bool = False
    font_family: str = "Arial"

@dataclass
class CalibrationConfig:
    base_offset: float = -8575.0
    scale_factor: float = 1000.0

@dataclass
class DiabetesConfig:
    show_insulin: bool = False
    icr: float = 10.0
    isf: float = 50.0
    target_bg: float = 100.0

@dataclass
class NetworkConfig:
    wifi_ssid: str = ""
    wifi_pass: str = ""
    api_key: str = ""

@dataclass
class AppConfig:
    hardware: HardwareConfig
    filters: FilterConfig
    ui: UIConfig
    calibration: CalibrationConfig
    diabetes: DiabetesConfig
    network: NetworkConfig
    base_dir: str

def _default_config() -> AppConfig:
    return AppConfig(
        hardware=HardwareConfig(),
        filters=FilterConfig(),
        ui=UIConfig(),
        calibration=CalibrationConfig(),
        diabetes=DiabetesConfig(),
        network=NetworkConfig(),
        base_dir=str(Path("~/bascula-cam").expanduser())
    )

def load_config() -> AppConfig:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists():
        try:
            raw = json.loads(CONFIG_PATH.read_text())
            return AppConfig(
                hardware=HardwareConfig(**raw.get("hardware", {})),
                filters=FilterConfig(**raw.get("filters", {})),
                ui=UIConfig(**raw.get("ui", {})),
                calibration=CalibrationConfig(**raw.get("calibration", {})),
                diabetes=DiabetesConfig(**raw.get("diabetes", {})),
                network=NetworkConfig(**raw.get("network", {})),
                base_dir=raw.get("base_dir", str(Path("~/bascula-cam").expanduser()))
            )
        except Exception:
            pass
    cfg = _default_config()
    save_config(cfg)
    return cfg

def save_config(cfg: AppConfig) -> None:
    payload = {
        "hardware": asdict(cfg.hardware),
        "filters": asdict(cfg.filters),
        "ui": asdict(cfg.ui),
        "calibration": asdict(cfg.calibration),
        "diabetes": asdict(cfg.diabetes),
        "network": asdict(cfg.network),
        "base_dir": cfg.base_dir,
    }
    CONFIG_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False))

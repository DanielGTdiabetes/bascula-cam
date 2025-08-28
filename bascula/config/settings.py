from pathlib import Path
from dataclasses import dataclass, asdict
import json

@dataclass
class CalibrationConfig:
    base_offset: float = -8575
    scale_factor: float = 400.0

@dataclass
class AppConfig:
    calibration: CalibrationConfig
    base_dir: Path

    def save(self, filepath: Path):
        with open(filepath, 'w') as f:
            json.dump(asdict(self), f, indent=2)

    @classmethod
    def load(cls, filepath: Path):
        if not filepath.exists():
            return cls.default()
        with open(filepath, 'r') as f:
            data = json.load(f)
        return cls(
            calibration=CalibrationConfig(**data.get("calibration", {})),
            base_dir=Path(data.get("base_dir", "~/bascula-cam")).expanduser()
        )

    @classmethod
    def default(cls):
        return cls(
            calibration=CalibrationConfig(),
            base_dir=Path("~/bascula-cam").expanduser()
        )

def load_config() -> AppConfig:
    config_path = Path("~/.bascula/config.json").expanduser()
    config_path.parent.mkdir(exist_ok=True)
    return AppConfig.load(config_path)

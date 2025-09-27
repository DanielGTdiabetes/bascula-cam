"""Configuration management for the Bascula application."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict

log = logging.getLogger(__name__)

CONFIG_DIR = Path(os.environ.get("BASCULA_SETTINGS_DIR", Path.home() / ".bascula"))
CONFIG_PATH = CONFIG_DIR / "config.json"
BACKUP_PATH = CONFIG_DIR / "config.json.bak"


@dataclass
class GeneralSettings:
    """General UI behaviour."""

    sound_enabled: bool = True
    volume: int = 70
    tts_enabled: bool = True


@dataclass
class ScaleSettings:
    """Persistent settings for the scale subsystem."""

    calibration_factor: float = 1.0
    decimals: int = 0
    unit_mode: str = "g"
    ml_factor: float = 1.0
    esp32_port: str = "/dev/ttyUSB0"
    hx711_dout: int = 5
    hx711_sck: int = 6


@dataclass
class NetworkSettings:
    """Mini-web and connectivity settings."""

    miniweb_enabled: bool = True
    miniweb_port: int = 8080
    miniweb_pin: str = "1234"


@dataclass
class DiabetesSettings:
    """Nightscout integration and diabetes assistant settings."""

    diabetes_enabled: bool = False
    ns_url: str = ""
    ns_token: str = ""
    hypo_alarm: int = 70
    hyper_alarm: int = 180
    mode_15_15: bool = False
    insulin_ratio: float = 12.0
    insulin_sensitivity: float = 50.0
    target_glucose: int = 110


@dataclass
class AudioSettings:
    """Audio playback configuration."""

    audio_device: str = "default"


@dataclass
class Settings:
    """Top level application settings dataclass."""

    general: GeneralSettings = field(default_factory=GeneralSettings)
    scale: ScaleSettings = field(default_factory=ScaleSettings)
    network: NetworkSettings = field(default_factory=NetworkSettings)
    diabetes: DiabetesSettings = field(default_factory=DiabetesSettings)
    audio: AudioSettings = field(default_factory=AudioSettings)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def save(self, path: Path = CONFIG_PATH) -> None:
        """Persist the settings to disk with backup on corruption."""

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        payload = self.to_dict()
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp_path.replace(path)
        log.info("Settings saved to %s", path)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Settings":
        def load_section(section: type, data: Dict[str, Any]) -> Any:
            field_names = {f.name for f in section.__dataclass_fields__.values()}
            filtered = {k: v for k, v in (data or {}).items() if k in field_names}
            return section(**filtered)

        return cls(
            general=load_section(GeneralSettings, payload.get("general", {})),
            scale=load_section(ScaleSettings, payload.get("scale", {})),
            network=load_section(NetworkSettings, payload.get("network", {})),
            diabetes=load_section(DiabetesSettings, payload.get("diabetes", {})),
            audio=load_section(AudioSettings, payload.get("audio", {})),
        )

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "Settings":
        """Load settings from disk, gracefully recovering on corruption."""

        try:
            raw = path.read_text(encoding="utf-8")
            payload = json.loads(raw)
            log.info("Loaded settings from %s", path)
            return cls.from_dict(payload)
        except FileNotFoundError:
            log.warning("Settings file %s missing, generating defaults", path)
        except json.JSONDecodeError as exc:
            log.error("Settings file %s corrupt: %s", path, exc)
            if path.exists():
                BACKUP_PATH.write_bytes(path.read_bytes())
                path.unlink()
        except Exception as exc:  # pragma: no cover - defensive
            log.exception("Unexpected error reading settings: %s", exc)

        defaults = cls()
        defaults.save(path)
        return defaults


__all__ = [
    "Settings",
    "GeneralSettings",
    "ScaleSettings",
    "NetworkSettings",
    "DiabetesSettings",
    "AudioSettings",
    "CONFIG_PATH",
]

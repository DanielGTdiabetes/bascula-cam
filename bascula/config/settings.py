"""Robust configuration handling for the Bascula application."""
from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Literal

log = logging.getLogger(__name__)

CONFIG_DIR = Path(os.environ.get("BASCULA_SETTINGS_DIR", Path.home() / ".bascula"))
CONFIG_PATH = CONFIG_DIR / "config.json"
BACKUP_PATH = CONFIG_DIR / "config.json.bak"


@dataclass
class GeneralSettings:
    """UI and interaction parameters."""

    sound_enabled: bool = True
    volume: int = 70
    tts_enabled: bool = True


@dataclass
class ScaleSettings:
    """Persistent configuration for the scale subsystem."""

    port: str = "__dummy__"
    baud: int = 115200
    hx711_dt: int = 5
    hx711_sck: int = 6
    calib_factor: float = 1.0
    smoothing: int = 5
    decimals: int = 0
    unit: Literal["g", "ml"] = "g"
    ml_factor: float = 1.0

    def __post_init__(self) -> None:
        try:
            self.baud = int(self.baud)
        except Exception:
            self.baud = 115200
        try:
            self.hx711_dt = int(self.hx711_dt)
        except Exception:
            self.hx711_dt = 5
        try:
            self.hx711_sck = int(self.hx711_sck)
        except Exception:
            self.hx711_sck = 6
        try:
            self.calib_factor = float(self.calib_factor)
        except Exception:
            self.calib_factor = 1.0
        if abs(self.calib_factor) < 1e-6:
            self.calib_factor = 1.0
        try:
            self.smoothing = max(1, int(self.smoothing))
        except Exception:
            self.smoothing = 5
        try:
            self.decimals = 1 if int(self.decimals) > 0 else 0
        except Exception:
            self.decimals = 0
        if (self.unit or "g").lower() not in {"g", "ml"}:
            self.unit = "g"
        else:
            self.unit = "ml" if str(self.unit).lower() == "ml" else "g"
        try:
            self.ml_factor = float(self.ml_factor)
        except Exception:
            self.ml_factor = 1.0
        if self.ml_factor <= 0:
            self.ml_factor = 1.0

    @property
    def calibration_factor(self) -> float:
        return self.calib_factor

    @calibration_factor.setter
    def calibration_factor(self, value: float) -> None:
        self.calib_factor = float(value)

    @property
    def unit_mode(self) -> str:
        return self.unit

    @unit_mode.setter
    def unit_mode(self, value: str) -> None:
        value = (value or "g").lower()
        self.unit = "ml" if value == "ml" else "g"


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
    voice_model: str = ""


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

    # ------------------------------------------------------------------
    @staticmethod
    def _atomic_save(payload: Dict[str, Any], path: Path) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(path)

    # ------------------------------------------------------------------
    def save(self, path: Path = CONFIG_PATH) -> None:
        """Persist the settings to disk atomically."""

        payload = self.to_dict()
        existing: Dict[str, Any] = {}
        try:
            raw = path.read_text(encoding="utf-8")
            loaded = json.loads(raw)
            if isinstance(loaded, dict):
                existing = loaded
        except FileNotFoundError:
            existing = {}
        except Exception:
            log.debug("Could not read existing settings before save", exc_info=True)
            existing = {}

        updated = _deep_update(existing, payload)
        scale_existing = existing.get("scale") if isinstance(existing.get("scale"), dict) else {}
        scale_payload = payload.get("scale") if isinstance(payload.get("scale"), dict) else {}
        scale_updated_obj = updated.get("scale")
        if not isinstance(scale_updated_obj, dict):
            scale_updated_obj = {}
            updated["scale"] = scale_updated_obj
        scale_updated = scale_updated_obj
        previous_port = None
        if isinstance(scale_existing, dict):
            previous_port = scale_existing.get("port")
        new_port = scale_payload.get("port") if isinstance(scale_payload, dict) else None
        if new_port in {None, "", "__dummy__"}:
            if previous_port not in {None, "", "__dummy__"}:
                scale_updated["port"] = previous_port
            else:
                scale_updated.pop("port", None)

        self._atomic_save(updated, path)
        log.info("Settings saved to %s", path)

    # ------------------------------------------------------------------
    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Settings":
        def load_section(section: type, data: Dict[str, Any]) -> Any:
            if not isinstance(data, dict):
                data = {}
            if section is ScaleSettings:
                data = _normalize_scale_payload(dict(data))
            field_names = {f.name for f in section.__dataclass_fields__.values()}
            filtered = {k: v for k, v in data.items() if k in field_names}
            return section(**filtered)

        return cls(
            general=load_section(GeneralSettings, payload.get("general", {})),
            scale=load_section(ScaleSettings, payload.get("scale", {})),
            network=load_section(NetworkSettings, payload.get("network", {})),
            diabetes=load_section(DiabetesSettings, payload.get("diabetes", {})),
            audio=load_section(AudioSettings, payload.get("audio", {})),
        )

    # ------------------------------------------------------------------
    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "Settings":
        """Load settings from disk, regenerating defaults on corruption."""

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        defaults = cls()
        default_payload = defaults.to_dict()
        needs_resave = False

        try:
            raw = path.read_text(encoding="utf-8")
            if not raw.strip():
                raise ValueError("empty settings file")
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("settings payload must be a JSON object")
            log.info("Loaded settings from %s", path)
        except FileNotFoundError:
            log.warning("Settings file %s missing; regenerating defaults", path)
            payload = default_payload
            needs_resave = True
        except (json.JSONDecodeError, ValueError) as exc:
            log.warning("Settings file %s invalid (%s); regenerating defaults", path, exc)
            _backup_corrupt_file(path)
            payload = default_payload
            needs_resave = True
        except Exception as exc:  # pragma: no cover - defensive fallback
            log.exception("Unexpected error reading settings: %s", exc)
            payload = default_payload
            needs_resave = True

        merged = _merge_defaults(default_payload, payload)
        settings = cls.from_dict(merged)

        if merged != payload or needs_resave:
            try:
                cls._atomic_save(merged, path)
            except Exception:  # pragma: no cover - defensive
                log.exception("Could not persist regenerated configuration")

        scale = settings.scale
        log.info(
            "Scale config: port=%s dt=%s sck=%s calib=%.4f decimals=%s unit=%s",
            scale.port or "",
            scale.hx711_dt,
            scale.hx711_sck,
            scale.calib_factor,
            scale.decimals,
            scale.unit,
        )
        return settings


# ----------------------------------------------------------------------
def _backup_corrupt_file(path: Path) -> None:
    try:
        if path.exists():
            BACKUP_PATH.write_bytes(path.read_bytes())
            path.unlink()
    except Exception:  # pragma: no cover - best effort
        log.debug("Could not create backup for corrupt settings", exc_info=True)


def _deep_update(original: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = dict(original)
    for key, value in updates.items():
        if isinstance(value, dict):
            base = result.get(key, {})
            if not isinstance(base, dict):
                base = {}
            result[key] = _deep_update(base, value)
        else:
            result[key] = value
    return result


def _merge_defaults(defaults: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    def merge_dict(default: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
        result: Dict[str, Any] = dict(default)
        for key, value in data.items():
            if key in default:
                if isinstance(default[key], dict) and isinstance(value, dict):
                    result[key] = merge_dict(default[key], value)
                else:
                    result[key] = value
            else:
                result[key] = value
        return result

    return merge_dict(defaults, payload or {})


def _normalize_scale_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    if "calibration_factor" in data and "calib_factor" not in data:
        data["calib_factor"] = data.pop("calibration_factor")
    if "density" in data and "ml_factor" not in data:
        data["ml_factor"] = data.pop("density")
    if "unit_mode" in data and "unit" not in data:
        data["unit"] = data.pop("unit_mode")
    if "esp32_port" in data and "port" not in data:
        data["port"] = data.pop("esp32_port")
    if "hx711_dout" in data and "hx711_dt" not in data:
        data["hx711_dt"] = data.pop("hx711_dout")
    if "hx711_dt_pin" in data and "hx711_dt" not in data:
        data["hx711_dt"] = data.pop("hx711_dt_pin")
    if "hx711_sck_pin" in data and "hx711_sck" not in data:
        data["hx711_sck"] = data.pop("hx711_sck_pin")
    if "smoothing" in data:
        try:
            data["smoothing"] = max(1, int(data["smoothing"]))
        except Exception:
            data["smoothing"] = 5
    return data


__all__ = [
    "Settings",
    "GeneralSettings",
    "ScaleSettings",
    "NetworkSettings",
    "DiabetesSettings",
    "AudioSettings",
    "CONFIG_PATH",
]

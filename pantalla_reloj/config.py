"""Configuration helpers for Pantalla Reloj."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict

log = logging.getLogger(__name__)

CONFIG_DIR_ENV = "PANTALLA_RELOJ_CONFIG_DIR"
DEFAULT_CONFIG_DIR = Path("/opt/pantalla-reloj/config")
CONFIG_FILE_NAME = "config.json"
SECRETS_FILE_NAME = "secrets.json"

LEGACY_SECRET_PATHS = {
    "aemet_api_key": ("integrations", "aemet", "api_key"),
    "opensky_client_id": ("integrations", "opensky", "client_id"),
    "opensky_client_secret": ("integrations", "opensky", "client_secret"),
}


DEFAULT_CONFIG: Dict[str, Any] = {
    "integrations": {
        "aemet": {
            "enabled": False,
            "poll_interval": 900,
            "bbox": None,
            "last_error": None,
        },
        "opensky": {
            "enabled": False,
            "poll_interval": 120,
            "bbox": None,
            "last_error": None,
        },
    }
}


def get_config_dir() -> Path:
    """Return the directory that holds runtime configuration."""

    env = os.environ.get(CONFIG_DIR_ENV)
    if env:
        return Path(env)
    return DEFAULT_CONFIG_DIR


def get_config_path() -> Path:
    return get_config_dir() / CONFIG_FILE_NAME


def get_secrets_path() -> Path:
    return get_config_dir() / SECRETS_FILE_NAME


def ensure_config_dir() -> None:
    """Create the config directory if missing."""

    path = get_config_dir()
    path.mkdir(parents=True, exist_ok=True)


def _atomic_write(path: Path, payload: Dict[str, Any], *, mode: int | None = None) -> None:
    ensure_config_dir()
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
    if mode is not None:
        try:
            os.chmod(tmp, mode)
        except PermissionError:  # pragma: no cover - best effort in dev
            log.debug("Cannot chmod %s", tmp)
    tmp.replace(path)


def load_config() -> Dict[str, Any]:
    """Load the public configuration file."""

    path = get_config_path()
    if not path.exists():
        return json.loads(json.dumps(DEFAULT_CONFIG))
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        log.warning("Failed to load config.json from %s", path, exc_info=True)
        return json.loads(json.dumps(DEFAULT_CONFIG))
    if not isinstance(data, dict):
        return json.loads(json.dumps(DEFAULT_CONFIG))

    # Merge with defaults to avoid missing sections.
    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    merged.update({k: v for k, v in data.items() if isinstance(k, str)})
    integrations = merged.setdefault("integrations", {})
    defaults_integrations = DEFAULT_CONFIG.get("integrations", {})
    if isinstance(data.get("integrations"), dict):
        for key, value in data["integrations"].items():
            default_value = defaults_integrations.get(key, {}) if isinstance(defaults_integrations, dict) else {}
            if isinstance(value, dict):
                merged_section = integrations.setdefault(key, {})
                merged_section.update(default_value if isinstance(default_value, dict) else {})
                merged_section.update(value)
            else:
                integrations[key] = value
    return merged


def save_config(payload: Dict[str, Any]) -> None:
    """Persist the configuration to disk."""

    _atomic_write(get_config_path(), payload)


def migrate_legacy_secrets(load_secret: Any, save_secret: Any) -> None:
    """Move inline secrets from config.json into secrets.json."""

    config_path = get_config_path()
    if not config_path.exists():
        return

    config = load_config()
    migrated: list[str] = []

    for new_key, path in LEGACY_SECRET_PATHS.items():
        container: Any = config
        for token in path[:-1]:
            if not isinstance(container, dict):
                container = None
                break
            container = container.get(token)
        if not isinstance(container, dict):
            continue
        key = path[-1]
        value = container.get(key)
        if isinstance(value, str) and value:
            if load_secret(new_key) != value:
                save_secret(new_key, value)
            container.pop(key, None)
            migrated.append(new_key)

    if migrated:
        log.info("Migrated legacy secrets: %s", ", ".join(sorted(set(migrated))))
        save_config(config)

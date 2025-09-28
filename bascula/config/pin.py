"""Helpers for managing the mini-web PIN stored in the YAML config."""
from __future__ import annotations

import logging
import random
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

import requests
import yaml

log = logging.getLogger(__name__)

CONFIG_YAML_PATH = Path("/etc/bascula/config.yaml")
DEFAULT_PIN_LENGTH = 6
MIN_PIN_LENGTH = 4
MAX_PIN_LENGTH = 6
DEFAULT_FILE_MODE = 0o640
DEFAULT_RELOAD_URL = "http://127.0.0.1:8080/config/reload"
DEFAULT_RELOAD_TIMEOUT = 1.0


class PinPersistenceError(RuntimeError):
    """Raised when the PIN cannot be persisted to the YAML configuration."""


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
        if isinstance(data, dict):
            return data
    except Exception:
        log.debug("No se pudo leer %s", path, exc_info=True)
    return {}


def _write_yaml(
    path: Path,
    payload: Dict[str, Any],
    *,
    file_mode: int = DEFAULT_FILE_MODE,
    owner: Optional[str] = None,
    group: Optional[str] = None,
) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(payload, handle, sort_keys=False, allow_unicode=True)
        tmp_path.replace(path)
        try:
            path.chmod(file_mode)
        except PermissionError:
            log.debug("Sin permisos para chmod %s", path)
        if owner or group:
            try:
                shutil.chown(path, user=owner or None, group=group or None)
            except (LookupError, PermissionError, OSError):
                log.debug("Sin permisos para chown %s", path, exc_info=True)
    except Exception as exc:  # pragma: no cover - defensive
        raise PinPersistenceError(f"No se pudo escribir {path}: {exc}") from exc


def is_valid_pin(pin: str, *, min_length: int = MIN_PIN_LENGTH, max_length: int = MAX_PIN_LENGTH) -> bool:
    pin = str(pin or "").strip()
    return pin.isdigit() and min_length <= len(pin) <= max_length


def generate_pin(length: int = DEFAULT_PIN_LENGTH) -> str:
    rng = random.SystemRandom()
    return "".join(rng.choice("0123456789") for _ in range(length))


def ensure_miniweb_pin(
    *,
    config_path: Optional[Path] = None,
    file_mode: int = DEFAULT_FILE_MODE,
    owner: Optional[str] = None,
    group: Optional[str] = None,
    pin_factory: Optional[Callable[[int], str]] = None,
    length: int = DEFAULT_PIN_LENGTH,
    min_length: int = MIN_PIN_LENGTH,
    max_length: int = MAX_PIN_LENGTH,
) -> Tuple[str, bool]:
    """Ensure a valid PIN is present in the YAML configuration.

    Returns a tuple with the effective PIN and a flag indicating if it was freshly
    generated and written to disk.
    """

    path = config_path or CONFIG_YAML_PATH
    data = _load_yaml(path)
    network = data.get("network") if isinstance(data, dict) else {}
    if not isinstance(network, dict):
        network = {}

    raw_pin = str(network.get("miniweb_pin") or network.get("pin") or "").strip()
    if is_valid_pin(raw_pin, min_length=min_length, max_length=max_length):
        return raw_pin, False

    factory = pin_factory or generate_pin
    new_pin = factory(length)
    network["miniweb_pin"] = new_pin
    data = dict(data)
    data["network"] = dict(network)
    _write_yaml(path, data, file_mode=file_mode, owner=owner, group=group)
    return new_pin, True


def set_miniweb_pin(
    new_pin: str,
    *,
    config_path: Optional[Path] = None,
    file_mode: int = DEFAULT_FILE_MODE,
    owner: Optional[str] = None,
    group: Optional[str] = None,
    min_length: int = MIN_PIN_LENGTH,
    max_length: int = MAX_PIN_LENGTH,
) -> None:
    path = config_path or CONFIG_YAML_PATH
    if not is_valid_pin(new_pin, min_length=min_length, max_length=max_length):
        raise ValueError("El PIN debe contener solo dígitos y tener longitud válida")

    data = _load_yaml(path)
    if not isinstance(data, dict):
        data = {}
    network = data.get("network") if isinstance(data.get("network"), dict) else {}
    updated = dict(data)
    updated_network = dict(network)
    updated_network["miniweb_pin"] = str(new_pin)
    updated_network.pop("pin", None)
    updated["network"] = updated_network
    _write_yaml(path, updated, file_mode=file_mode, owner=owner, group=group)


def regenerate_miniweb_pin(
    *,
    config_path: Optional[Path] = None,
    file_mode: int = DEFAULT_FILE_MODE,
    owner: Optional[str] = None,
    group: Optional[str] = None,
    pin_factory: Optional[Callable[[int], str]] = None,
    length: int = DEFAULT_PIN_LENGTH,
) -> str:
    factory = pin_factory or generate_pin
    new_pin = factory(length)
    set_miniweb_pin(
        new_pin,
        config_path=config_path,
        file_mode=file_mode,
        owner=owner,
        group=group,
    )
    return new_pin


def reload_miniweb_config(
    *,
    url: str = DEFAULT_RELOAD_URL,
    timeout: float = DEFAULT_RELOAD_TIMEOUT,
) -> bool:
    try:
        response = requests.post(url, timeout=timeout)
        return bool(response.ok)
    except Exception:
        log.debug("No se pudo recargar la mini-web en %s", url, exc_info=True)
        return False


__all__ = [
    "CONFIG_YAML_PATH",
    "DEFAULT_FILE_MODE",
    "DEFAULT_PIN_LENGTH",
    "DEFAULT_RELOAD_TIMEOUT",
    "DEFAULT_RELOAD_URL",
    "MAX_PIN_LENGTH",
    "MIN_PIN_LENGTH",
    "PinPersistenceError",
    "ensure_miniweb_pin",
    "generate_pin",
    "is_valid_pin",
    "regenerate_miniweb_pin",
    "reload_miniweb_config",
    "set_miniweb_pin",
]

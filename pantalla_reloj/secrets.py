"""Secret storage helpers."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Dict, Optional

from .config import _atomic_write, ensure_config_dir, get_secrets_path

log = logging.getLogger(__name__)


def _read_secrets(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)
    except Exception:
        log.warning("Failed to read secrets from %s", path, exc_info=True)
        return {}
    if not isinstance(payload, dict):
        return {}
    result: Dict[str, str] = {}
    for key, value in payload.items():
        if isinstance(key, str) and isinstance(value, str):
            result[key] = value
    return result


def load_secrets() -> Dict[str, str]:
    """Return the entire secrets dictionary."""

    return _read_secrets(get_secrets_path())


def load_secret(key: str) -> Optional[str]:
    """Fetch a single secret value."""

    return load_secrets().get(key)


def save_secret(key: str, value: str) -> None:
    """Persist a secret to disk using atomic writes and secure permissions."""

    if not key:
        raise ValueError("Secret key is required")
    cleaned = value.strip()
    secrets = load_secrets()
    if not cleaned:
        secrets.pop(key, None)
        _write_secrets(secrets)
        return
    secrets[key] = cleaned
    _write_secrets(secrets)


def delete_secret(key: str) -> None:
    secrets = load_secrets()
    if key in secrets:
        secrets.pop(key, None)
        _write_secrets(secrets)


def _write_secrets(payload: Dict[str, str]) -> None:
    path = get_secrets_path()
    ensure_config_dir()
    _atomic_write(path, payload, mode=0o600)
    try:
        os.chmod(path, 0o600)
    except PermissionError:  # pragma: no cover - dev machines might not allow
        log.debug("Cannot chmod %s", path)

"""Helpers to keep the standalone miniweb PIN in sync."""

from __future__ import annotations

import json
import logging
import os
import random
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from bascula.config.settings import CONFIG_PATH, Settings

log = logging.getLogger(__name__)


DEFAULT_AUTH_PATH = Path("/var/lib/bascula/miniweb/auth.json")
DEFAULT_DIR_MODE = 0o750
DEFAULT_FILE_MODE = 0o640


def _normalize_pin(value: Optional[str]) -> str:
    if value is None:
        return ""
    pin = str(value).strip()
    return pin


def _load_auth_payload(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except Exception:
        log.debug("No se pudo leer %s", path, exc_info=True)
    return {}


def _write_auth_payload(path: Path, payload: Dict[str, Any], *, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    try:
        path.chmod(mode)
    except PermissionError:
        log.debug("Sin permisos para chmod %s", path)


def _ensure_ownership(path: Path, *, owner: Optional[str], group: Optional[str]) -> None:
    if owner is None and group is None:
        return
    try:
        shutil.chown(path, user=owner or None, group=group or None)
    except (LookupError, PermissionError, OSError):
        log.debug("Sin permisos para chown %s", path, exc_info=True)


def _generate_pin(min_digits: int = 4, max_digits: int = 6) -> str:
    rng = random.SystemRandom()
    length = rng.randint(min_digits, max_digits)
    lower = 10 ** (length - 1)
    upper = (10 ** length) - 1
    return f"{rng.randint(lower, upper):0{length}d}"


def sync_miniweb_pin(
    settings: Settings,
    *,
    auth_path: Path | None = None,
    config_path: Path | None = None,
    owner: Optional[str] = None,
    group: Optional[str] = None,
    file_mode: int = DEFAULT_FILE_MODE,
    dir_mode: int = DEFAULT_DIR_MODE,
    save_settings: bool = True,
    prefer_config: bool = False,
) -> str:
    """Ensure the config.json and auth.json pins stay in sync.

    Returns the effective PIN after synchronisation.
    """

    auth_file = auth_path or DEFAULT_AUTH_PATH
    cfg_path = config_path or CONFIG_PATH

    auth_file.parent.mkdir(parents=True, exist_ok=True)

    auth_payload = _load_auth_payload(auth_file)
    auth_pin = _normalize_pin(auth_payload.get("pin")) if isinstance(auth_payload, dict) else ""

    config_pin = _normalize_pin(getattr(settings.network, "miniweb_pin", ""))

    if prefer_config:
        final_pin = config_pin or auth_pin or ""
    else:
        final_pin = auth_pin or config_pin or ""

    if not final_pin:
        final_pin = _generate_pin()

    settings_changed = False
    if final_pin != config_pin:
        settings.network.miniweb_pin = final_pin
        settings_changed = True

    if not isinstance(auth_payload, dict):
        auth_payload = {}

    if auth_payload.get("pin") != final_pin or not auth_file.exists():
        auth_payload = dict(auth_payload)
        auth_payload["pin"] = final_pin
        auth_payload["updated_at"] = datetime.now(tz=timezone.utc).isoformat()
        _write_auth_payload(auth_file, auth_payload, mode=file_mode)
    else:
        try:
            auth_file.chmod(file_mode)
        except PermissionError:
            log.debug("Sin permisos para chmod %s", auth_file)

    try:
        auth_file.parent.chmod(dir_mode)
    except PermissionError:
        log.debug("Sin permisos para chmod %s", auth_file.parent)

    _ensure_ownership(auth_file.parent, owner=owner, group=group)
    _ensure_ownership(auth_file, owner=owner, group=group)

    if settings_changed and save_settings:
        try:
            settings.save(cfg_path)
        except Exception:
            log.exception("No se pudo guardar la configuración tras sincronizar el PIN")

    return final_pin


__all__ = ["sync_miniweb_pin", "DEFAULT_AUTH_PATH", "DEFAULT_FILE_MODE", "DEFAULT_DIR_MODE"]

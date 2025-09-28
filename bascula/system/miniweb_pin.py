"""Backward compatible helpers to manage the mini-web PIN."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Optional

from bascula.config.pin import (
    CONFIG_YAML_PATH,
    DEFAULT_FILE_MODE,
    PinPersistenceError,
    ensure_miniweb_pin,
    is_valid_pin,
    set_miniweb_pin,
)
from bascula.config.settings import CONFIG_PATH, Settings

log = logging.getLogger(__name__)

DEFAULT_DIR_MODE = 0o750


def _apply_dir_permissions(path: Path, *, mode: int, owner: Optional[str], group: Optional[str]) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except Exception:
        log.debug("No se pudo crear el directorio %s", path, exc_info=True)
        return
    try:
        path.chmod(mode)
    except PermissionError:
        log.debug("Sin permisos para chmod %s", path)
    if owner or group:
        try:
            shutil.chown(path, user=owner or None, group=group or None)
        except (LookupError, PermissionError, OSError):
            log.debug("Sin permisos para chown %s", path, exc_info=True)


def sync_miniweb_pin(
    settings: Settings,
    *,
    config_path: Optional[Path] = None,
    owner: Optional[str] = None,
    group: Optional[str] = None,
    file_mode: int = DEFAULT_FILE_MODE,
    dir_mode: int = DEFAULT_DIR_MODE,
    save_settings: bool = True,
    prefer_config: bool = False,
) -> str:
    """Synchronise the Settings object with the YAML-stored PIN."""

    yaml_path = config_path or CONFIG_YAML_PATH
    desired_pin = str(getattr(settings.network, "miniweb_pin", "") or "").strip()

    try:
        config_pin, _ = ensure_miniweb_pin(
            config_path=yaml_path,
            file_mode=file_mode,
            owner=owner,
            group=group,
        )
    except PinPersistenceError:
        log.exception("No se pudo garantizar el PIN de la mini-web en %s", yaml_path)
        config_pin = ""

    final_pin = config_pin

    if not prefer_config and is_valid_pin(desired_pin):
        if desired_pin != config_pin:
            try:
                set_miniweb_pin(
                    desired_pin,
                    config_path=yaml_path,
                    file_mode=file_mode,
                    owner=owner,
                    group=group,
                )
                final_pin = desired_pin
            except (ValueError, PinPersistenceError):
                log.exception("No se pudo actualizar el PIN de la mini-web en %s", yaml_path)
        else:
            final_pin = config_pin
    else:
        final_pin = config_pin if is_valid_pin(config_pin) else desired_pin

    if not is_valid_pin(final_pin):
        final_pin = config_pin or desired_pin

    settings.network.miniweb_pin = final_pin or ""

    if save_settings:
        try:
            settings.save(CONFIG_PATH)
        except Exception:
            log.exception("No se pudo guardar la configuración tras sincronizar el PIN")

    _apply_dir_permissions(yaml_path.parent, mode=dir_mode, owner=owner, group=group)
    return final_pin


__all__ = ["sync_miniweb_pin", "DEFAULT_DIR_MODE", "DEFAULT_FILE_MODE"]

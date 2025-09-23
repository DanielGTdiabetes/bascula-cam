"""Utility helpers to load Tk icons with automatic fallbacks."""
from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

import tkinter as tk

log = logging.getLogger(__name__)

_ROOT_DIR = Path(__file__).resolve().parents[2]
_ICON_DIR = _ROOT_DIR / "assets" / "icons"
_ICON_CACHE: Dict[Tuple[str, int], tk.PhotoImage] = {}
_FALLBACK_ATTEMPTED = False


def _candidate_paths(name: str) -> Tuple[Path, Path]:
    primary = _ICON_DIR / f"{name}.png"
    secondary = _ICON_DIR / "topbar" / f"{name}.png"
    return primary, secondary


def _resolve_icon_path(name: str) -> Optional[Path]:
    for path in _candidate_paths(name):
        if path.exists():
            return path
    return None


def _resize_if_needed(image: tk.PhotoImage, size: int) -> tk.PhotoImage:
    if size <= 0:
        return image
    width, height = image.width(), image.height()
    if width == size and height == size:
        return image

    try:
        if width >= size and height >= size and width % size == 0 and height % size == 0:
            factor = width // size
            return image.subsample(max(1, factor), max(1, factor))
        if width <= size and height <= size and size % width == 0 and size % height == 0:
            factor = size // width
            return image.zoom(max(1, factor), max(1, factor))
    except Exception as exc:  # pragma: no cover - Tk runtime guard
        log.debug("No se pudo redimensionar icono %s: %s", image, exc)
    return image


def _load_photo(path: Path, size: int) -> Optional[tk.PhotoImage]:
    try:
        image = tk.PhotoImage(file=str(path))
    except Exception as exc:  # pragma: no cover - Tk runtime guard
        log.debug("Carga de icono fallida %s: %s", path, exc)
        return None
    return _resize_if_needed(image, size)


def _ensure_fallback_icons() -> None:
    global _FALLBACK_ATTEMPTED
    if _FALLBACK_ATTEMPTED:
        return
    _FALLBACK_ATTEMPTED = True
    try:
        subprocess.run(
            [sys.executable, "-m", "scripts.write_icons", "--out", str(_ICON_DIR)],
            check=True,
            cwd=str(_ROOT_DIR),
        )
    except Exception as exc:  # pragma: no cover - CLI guard
        log.warning("No se pudieron generar iconos de fallback: %s", exc)


def load_icon(name: str, size: int = 32) -> Optional[tk.PhotoImage]:
    """Load an icon image, generating fallbacks if necessary."""

    key = (name, size)
    cached = _ICON_CACHE.get(key)
    if cached is not None:
        return cached

    path = _resolve_icon_path(name)
    image = _load_photo(path, size) if path else None

    if image is None:
        _ensure_fallback_icons()
        path = _resolve_icon_path(name)
        image = _load_photo(path, size) if path else None

    if image is None:
        return None

    _ICON_CACHE[key] = image
    return image


__all__ = ["load_icon"]

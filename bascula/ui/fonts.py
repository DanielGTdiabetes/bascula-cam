"""Utility helpers for locating UI fonts with graceful fallback."""
from __future__ import annotations

import logging
import subprocess
from functools import lru_cache

log = logging.getLogger(__name__)


_PREFERRED_UI_FONTS = ("Oxanium", "DejaVu Sans")
_PREFERRED_MONO_FONTS = ("Share Tech Mono", "DejaVu Sans Mono")


def _fc_match(font_name: str) -> str | None:
    """Return the best match for a font family using ``fc-match``.

    The function is defensive so that the UI can still be created on
    platforms without fontconfig.
    """

    try:
        result = subprocess.check_output(
            ["fc-match", "-f", "%{family}", font_name],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except FileNotFoundError:
        log.debug("fc-match no disponible; usando fallback seguro")
        return None
    except subprocess.CalledProcessError:
        return None
    except Exception:  # pragma: no cover - seguridad
        log.debug("No se pudo resolver la fuente %s", font_name, exc_info=True)
        return None

    if not result:
        return None
    return result.split(",")[0].strip()


@lru_cache(maxsize=1)
def get_ui_font_family() -> str:
    """Return the preferred UI font family with fallback."""

    for font in _PREFERRED_UI_FONTS:
        match = _fc_match(font)
        if match:
            return match
    return _PREFERRED_UI_FONTS[-1]


@lru_cache(maxsize=1)
def get_mono_font_family() -> str:
    """Return the preferred monospaced font family with fallback."""

    for font in _PREFERRED_MONO_FONTS:
        match = _fc_match(font)
        if match:
            return match
    return _PREFERRED_MONO_FONTS[-1]


def font_tuple(size: int, weight: str = "normal") -> tuple[str, int, str] | tuple[str, int]:
    """Return a tuple describing the UI font using the preferred family."""

    family = get_ui_font_family()
    if weight and weight.lower() != "normal":
        return (family, size, weight)
    return (family, size)


def mono_font_tuple(size: int, weight: str = "normal") -> tuple[str, int, str] | tuple[str, int]:
    """Return the monospaced font tuple using the preferred family."""

    family = get_mono_font_family()
    if weight and weight.lower() != "normal":
        return (family, size, weight)
    return (family, size)


__all__ = [
    "get_ui_font_family",
    "get_mono_font_family",
    "font_tuple",
    "mono_font_tuple",
]


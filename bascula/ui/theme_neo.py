"""Modern Báscula UI theme constants and helpers."""
from __future__ import annotations

from typing import Tuple

COLORS = {
    "bg": "#0b0f14",
    "surface": "#121721",
    "primary": "#00c2a8",
    "text": "#e5f1ff",
    "muted": "#99a7b3",
    "danger": "#ff5566",
}

SPACING = {
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
}

FONTS = {
    "sans": "DejaVu Sans",
    "mono": "DejaVu Sans Mono",
}


def _ensure_int(value: int | float | str) -> int:
    try:
        return int(round(float(value)))
    except Exception:
        raise ValueError(f"Font size must be numeric, got {value!r}") from None


def safe_color(value: str | None, fallback: str | None = None) -> str:
    """Return a Tk friendly color string.

    The function only accepts hexadecimal color strings ("#RRGGBB" or "#RGB").
    When an invalid value is provided the fallback color (or theme surface color)
    is returned instead.
    """

    candidate = (value or "").strip()
    if candidate:
        hex_part = candidate[1:]
        if candidate.startswith("#") and len(hex_part) in (3, 6):
            try:
                int(hex_part, 16)
            except ValueError:
                candidate = ""
            else:
                return candidate.lower() if len(hex_part) == 6 else candidate
    fallback_color = (fallback or COLORS["surface"]).strip() or COLORS["surface"]
    return fallback_color


def font_sans(size: int | float | str, weight: str = "normal") -> Tuple[str, int, str]:
    """Return a tuple suitable for Tk font configuration using the sans family."""

    return (FONTS["sans"], _ensure_int(size), str(weight))


def font_mono(size: int | float | str, weight: str = "normal") -> Tuple[str, int, str]:
    """Return a tuple suitable for Tk font configuration using the mono family."""

    return (FONTS["mono"], _ensure_int(size), str(weight))

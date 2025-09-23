"""Modern Báscula UI theme constants and helpers."""
from __future__ import annotations

from typing import Tuple

# Base palette following WCAG AA contrast ratios for primary surfaces.
COLORS = {
    "bg": "#0B0F14",
    "fg": "#E6EDF3",
    "accent": "#3BA0FF",
    "muted": "#8CA0B3",
    "danger": "#FF5577",
    # Compatibility aliases used across the legacy UI code paths.
    "surface": "#111722",
    "surface_alt": "#161C29",
    "primary": "#3BA0FF",
    "text": "#E6EDF3",
}

SPACING = {
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 24,
}

FONTS = {
    "display": ("Inter", 64, "bold"),
    "h1": ("Inter", 28, "bold"),
    "h2": ("Inter", 22, "bold"),
    "body": ("Inter", 16, "normal"),
    "btn": ("Inter", 20, "bold"),
    # Backwards compatibility fallbacks.
    "sans": "Inter",
    "mono": "JetBrains Mono",
}


def _ensure_int(value: int | float | str) -> int:
    try:
        return int(round(float(value)))
    except Exception:  # pragma: no cover - defensive parsing
        raise ValueError(f"Font size must be numeric, got {value!r}") from None


def safe_color(value: str | None, fallback: str | None = None) -> str:
    """Return a Tk friendly color string."""

    candidate = (value or "").strip()
    if candidate:
        hex_part = candidate[1:]
        if candidate.startswith("#") and len(hex_part) in (3, 6):
            try:
                int(hex_part, 16)
            except ValueError:
                candidate = ""
            else:
                return candidate.upper() if len(hex_part) == 6 else candidate
    fallback_color = (fallback or COLORS["surface"]).strip() or COLORS["surface"]
    return fallback_color


def font_sans(size: int | float | str, weight: str = "normal") -> Tuple[str, int, str]:
    """Return a tuple suitable for Tk font configuration using the sans family."""

    family = FONTS.get("sans", FONTS["body"][0])
    return (family, _ensure_int(size), str(weight))


def font_mono(size: int | float | str, weight: str = "normal") -> Tuple[str, int, str]:
    """Return a tuple suitable for Tk font configuration using the mono family."""

    family = FONTS.get("mono", "JetBrains Mono")
    return (family, _ensure_int(size), str(weight))


def _relative_luminance(hex_color: str) -> float:
    value = safe_color(hex_color)
    rgb = [int(value[i : i + 2], 16) / 255.0 for i in (1, 3, 5)]
    channel = []
    for component in rgb:
        if component <= 0.03928:
            channel.append(component / 12.92)
        else:
            channel.append(((component + 0.055) / 1.055) ** 2.4)
    r, g, b = channel
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def wcag_contrast(color_1: str, color_2: str) -> float:
    """Return the WCAG contrast ratio between two colors."""

    lum1 = _relative_luminance(color_1)
    lum2 = _relative_luminance(color_2)
    lighter, darker = (lum1, lum2) if lum1 > lum2 else (lum2, lum1)
    return round((lighter + 0.05) / (darker + 0.05), 2)


_CONTRAST_BG_FG = wcag_contrast(COLORS["bg"], COLORS["fg"])
if _CONTRAST_BG_FG < 4.5:  # pragma: no cover - executed at import time
    raise RuntimeError(
        f"theme_neo contrast ratio too low: bg/fg {_CONTRAST_BG_FG}."
        " Expected >= 4.5."
    )


__all__ = [
    "COLORS",
    "SPACING",
    "FONTS",
    "font_sans",
    "font_mono",
    "safe_color",
    "wcag_contrast",
]

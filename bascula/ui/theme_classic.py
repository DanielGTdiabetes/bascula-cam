"""Classic Tk theme helpers for Báscula Cam."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Tuple

FONT_MONO = ("DejaVu Sans Mono", 14, "normal")
FONT_UI = ("DejaVu Sans", 14, "normal")
SIZES = {"xxl": 64, "xl": 32, "lg": 20, "md": 16, "sm": 14, "xs": 12}


@dataclass(frozen=True, slots=True)
class Spacing:
    gutter: int = 16
    padding: int = 12
    nav_height: int = 64
    header_height: int = 48


COLORS = {
    "bg": "#f0f0f0",
    "surface": "#ffffff",
    "surface_alt": "#f4f4f4",
    "accent": "#0078d4",
    "accent_dim": "#005a9e",
    "accent_fg": "#ffffff",
    "text": "#202020",
    "muted": "#5a5a5a",
    "warning": "#d83b01",
    "success": "#107c10",
    "divider": "#d0d0d0",
}

SPACING = Spacing()


def coerce_int(value: Any, fallback: int) -> int:
    """Attempt to coerce *value* to an int, logging fallbacks elsewhere."""

    try:
        if isinstance(value, bool):
            raise TypeError
        return int(float(value))
    except (TypeError, ValueError):
        return int(fallback)


def normalize_font(value: Any, fallback: Tuple[str, int, str]) -> Tuple[Any, ...]:
    family, size, weight = fallback
    extras: list[str] = []
    if isinstance(value, str):
        candidate = value.strip()
        if candidate:
            return (candidate, size, weight)
        return (family, size, weight)
    if isinstance(value, (tuple, list)):
        if value:
            candidate_family = str(value[0]).strip()
            if candidate_family:
                family = candidate_family
        if len(value) >= 2:
            size = coerce_int(value[1], size)
        if len(value) >= 3:
            candidate_weight = str(value[2]).strip()
            if candidate_weight:
                weight = candidate_weight
        if len(value) > 3:
            extras = [str(part) for part in value[3:] if str(part)]
        return (family, size, weight, *extras)
    return (family, size, weight)


def font(size_key: str = "md", *, family: str = "ui", weight: str = "normal") -> Tuple[str, int, str]:
    base = FONT_UI if family != "mono" else FONT_MONO
    family_name = base[0]
    size = SIZES.get(size_key, base[1])
    return (family_name, size, weight)


def safe_color(value: str | None, fallback: str) -> str:
    if isinstance(value, str):
        candidate = value.strip()
        if candidate and candidate.lower() != "none":
            return candidate
    return fallback


def iter_font_sizes() -> Iterable[str]:
    return SIZES.keys()

"""Compatibility layer for legacy CRT themed helpers."""
from __future__ import annotations

from tkinter import Canvas, Misc
from typing import Iterable

from .theme_neo import COLORS as CRT_COLORS
from .theme_neo import SPACING as CRT_SPACING
from .theme_neo import font_mono as mono
from .theme_neo import font_sans as sans
from .theme_neo import safe_color

CRT_FONT_SIZES = {
    "xxl": 120,
    "xl": 48,
    "lg": 24,
    "md": 20,
    "sm": 18,
    "xs": 16,
}


def apply_crt_colors(widget: Misc, color_name: str = "bg") -> None:
    """Apply a background color to a widget using safe CRT mappings."""

    color = safe_color(CRT_COLORS.get(color_name), CRT_COLORS["bg"])
    try:
        widget.configure(bg=color)
    except Exception:
        # Some ttk widgets expose the configuration via set options
        try:
            widget["background"] = color  # type: ignore[index]
        except Exception:
            pass


def draw_dotted_rule(
    canvas: Canvas,
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    *,
    color: str | None = None,
    dash: Iterable[int] | None = (2, 2),
) -> int:
    """Draw a dotted line on the provided canvas returning the item id."""

    dash_pattern = tuple(dash) if dash else (2, 2)
    line_color = safe_color(color, CRT_COLORS["muted"])
    return canvas.create_line(x1, y1, x2, y2, fill=line_color, dash=dash_pattern)

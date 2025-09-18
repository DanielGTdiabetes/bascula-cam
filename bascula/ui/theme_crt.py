"""Theme definitions for the retro CRT look and feel."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


def _safe_color(value: str | None, fallback: str) -> str:
    if isinstance(value, str):
        trimmed = value.strip()
        if trimmed and trimmed.lower() != "none":
            if trimmed.startswith("#") and len(trimmed) in (4, 7):
                return trimmed
            return trimmed
    return fallback


CRT_COLORS: Dict[str, str] = {
    "bg": "#001a00",
    "surface": "#012b12",
    "surface_alt": "#01351a",
    "accent": "#00ff99",
    "accent_dim": "#00cc88",
    "accent_dark": "#009966",
    "text": "#bfffe2",
    "muted": "#7ac7a4",
    "warning": "#e2d75c",
    "error": "#ff6655",
    "info": "#36f9b5",
    "shadow": "#000c05",
    "divider": "#006644",
    "fallback": "#111111",
}


CRT_MONO_FALLBACK = "JetBrains Mono"
CRT_MONO_ALT = "DejaVu Sans Mono"
CRT_SANS_FALLBACK = "Inter"
CRT_SANS_ALT = "Fira Sans"


@dataclass(slots=True)
class FontStack:
    primary: str
    fallback: str

    def as_tuple(self, size: int, weight: str = "normal") -> Tuple[str, int, str]:
        return (self.primary or self.fallback, size, weight)


MONO_STACK = FontStack(primary=CRT_MONO_FALLBACK, fallback=CRT_MONO_ALT)
SANS_STACK = FontStack(primary=CRT_SANS_FALLBACK, fallback=CRT_SANS_ALT)


CRT_FONT_SIZES: Dict[str, int] = {
    "xxl": 48,
    "xl": 36,
    "lg": 28,
    "md": 22,
    "sm": 18,
    "xs": 16,
}


def mono(size_key: str, weight: str = "bold") -> Tuple[str, int, str]:
    size = CRT_FONT_SIZES.get(size_key, CRT_FONT_SIZES["md"])
    return MONO_STACK.as_tuple(size, weight)


def sans(size_key: str, weight: str = "normal") -> Tuple[str, int, str]:
    size = CRT_FONT_SIZES.get(size_key, CRT_FONT_SIZES["sm"])
    return SANS_STACK.as_tuple(size, weight)


@dataclass(frozen=True, slots=True)
class Spacing:
    gutter: int = 18
    padding: int = 16
    nav_height: int = 96
    header_height: int = 72


CRT_SPACING = Spacing()


def draw_dotted_rule(canvas, x0: int, y0: int, x1: int, *, color: str | None = None, size: int = 2, gap: int = 6) -> None:
    """Draw a dotted horizontal rule on a Tk canvas."""

    safe_color = _safe_color(color, CRT_COLORS["divider"])
    step = size + gap
    width = max(0, x1 - x0)
    dots = max(1, width // step)
    for index in range(dots + 1):
        cx = x0 + index * step
        canvas.create_rectangle(cx, y0, cx + size, y0 + size, outline="", fill=safe_color)


def apply_crt_colors(widget) -> None:
    """Apply default background/foreground colors to a widget."""

    try:
        widget.configure(bg=_safe_color(getattr(widget, "cget", lambda _name: None)("bg"), CRT_COLORS["bg"]))
    except Exception:
        try:
            widget.configure(bg=CRT_COLORS["bg"])
        except Exception:
            pass


def safe_color(name: str, fallback: str | None = None) -> str:
    base = CRT_COLORS.get(name)
    if fallback is None:
        fallback = CRT_COLORS["fallback"]
    return _safe_color(base, fallback)


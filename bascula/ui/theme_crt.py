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
    "bg": "#0A1F0F",
    "surface": "#0A1F0F",
    "surface_alt": "#0A1F0F",
    "accent": "#00FF88",
    "accent_dim": "#00CC66",
    "accent_dark": "#00CC66",
    "text": "#00FF88",
    "muted": "#00CC66",
    "warning": "#00CC66",
    "error": "#00CC66",
    "info": "#00CC66",
    "shadow": "#0A1F0F",
    "divider": "#00FF88",
    "fallback": "#0A1F0F",
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
    "xxl": 120,
    "xl": 48,
    "lg": 24,
    "md": 20,
    "sm": 18,
    "xs": 16,
}


def mono(size_key: str, weight: str = "bold") -> Tuple[str, int, str]:
    size = CRT_FONT_SIZES.get(size_key, CRT_FONT_SIZES["md"])
    return MONO_STACK.as_tuple(size, weight)


def sans(size_key: str, weight: str = "normal") -> Tuple[str, int, str]:
    size = CRT_FONT_SIZES.get(size_key, CRT_FONT_SIZES["sm"])
    return SANS_STACK.as_tuple(size, weight)


def font_mono(size: int = 14, weight: str = "normal") -> Tuple[str, int, str]:
    """Return a mono-spaced font tuple for raw Tk widgets."""

    base = MONO_STACK.primary or MONO_STACK.fallback
    return (base, size, weight)


@dataclass(frozen=True, slots=True)
class Spacing:
    gutter: int = 16
    padding: int = 16
    nav_height: int = 64
    header_height: int = 48


CRT_SPACING = Spacing()


def set_font_preferences(*, mono: str | None = None, sans: str | None = None) -> None:
    """Override the primary families used by mono()/sans()."""

    global MONO_STACK, SANS_STACK
    if mono:
        MONO_STACK = FontStack(primary=mono, fallback=CRT_MONO_ALT)
    if sans:
        SANS_STACK = FontStack(primary=sans, fallback=CRT_SANS_ALT)


def _assert_theme_sanity():
    assert isinstance(CRT_SPACING.padding, int)
    assert isinstance(CRT_SPACING.gutter, int)


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


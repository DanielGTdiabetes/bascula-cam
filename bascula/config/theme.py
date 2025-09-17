"""Simple theme helpers for the kiosk UI."""
from __future__ import annotations

from copy import deepcopy
import importlib
import os
from tkinter import ttk
import tkinter as tk

# Keys available for every theme.  ``BG/TEXT/ACCENT/BORDER`` are legacy names
# kept for compatibility with older widgets.  The extended palette is consumed
# by the modern UI components (cards, toasts, etc.).
_THEMES: dict[str, dict[str, str]] = {
    "modern": {
        "BG": "#0A0E1A",
        "TEXT": "#F0F4F8",
        "ACCENT": "#00D4AA",
        "BORDER": "#1F2636",
        "COL_BG": "#0A0E1A",
        "COL_CARD": "#141B2D",
        "COL_CARD_HOVER": "#1B2338",
        "COL_BORDER": "#1F2636",
        "COL_TEXT": "#F0F4F8",
        "COL_MUTED": "#98A7C2",
        "COL_ACCENT": "#00D4AA",
        "COL_SUCCESS": "#35D07F",
        "COL_WARN": "#F0AA3A",
        "COL_DANGER": "#F05B4F",
        "COL_SHADOW": "#00000040",
    },
    "retro": {
        "BG": "#050A04",
        "TEXT": "#8FFFA5",
        "ACCENT": "#66FFCC",
        "BORDER": "#0F3D1E",
        "COL_BG": "#050A04",
        "COL_CARD": "#0D1F11",
        "COL_CARD_HOVER": "#132916",
        "COL_BORDER": "#0F3D1E",
        "COL_TEXT": "#8FFFA5",
        "COL_MUTED": "#5A9B74",
        "COL_ACCENT": "#66FFCC",
        "COL_SUCCESS": "#6BE089",
        "COL_WARN": "#E9D76F",
        "COL_DANGER": "#F26C6C",
        "COL_SHADOW": "#00000060",
    },
}

_current_theme = "modern"


def list_themes() -> list[str]:
    """Return the available theme identifiers."""

    return sorted(_THEMES)


def colors() -> dict[str, str]:
    """Return a legacy palette compatible with the original application."""

    palette = get_current_colors()
    return {
        "BG": palette["COL_BG"],
        "TEXT": palette["COL_TEXT"],
        "ACCENT": palette["COL_ACCENT"],
        "BORDER": palette["COL_BORDER"],
    }


def get_current_colors() -> dict[str, str]:
    """Return a copy of the currently active extended palette."""

    return deepcopy(_THEMES[_current_theme])


def set_theme(name: str) -> str:
    """Select *name* as current theme, returning the resolved value."""

    global _current_theme
    if name not in _THEMES:
        name = os.environ.get("BASCULA_UI_THEME", _current_theme)
    if name not in _THEMES:
        name = "modern"
    _current_theme = name
    return name


def _configure_styles(palette: dict[str, str]) -> None:
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    bg = palette["COL_BG"]
    text = palette["COL_TEXT"]
    accent = palette["COL_ACCENT"]
    card = palette["COL_CARD"]
    border = palette["COL_BORDER"]

    style.configure("TFrame", background=bg, bordercolor=border)
    style.configure("Card.TFrame", background=card, bordercolor=border)
    style.configure("TLabel", background=bg, foreground=text)
    style.configure("Heading.TLabel", background=bg, foreground=text, font=("DejaVu Sans", 22, "bold"))
    style.configure(
        "TButton",
        background=accent,
        foreground=bg,
        bordercolor=accent,
        focusthickness=1,
        padding=(12, 8),
        font=("DejaVu Sans", 12, "bold"),
    )
    style.map(
        "TButton",
        background=[("active", palette["COL_CARD_HOVER"])],
        foreground=[("active", palette["COL_TEXT"])],
    )


def _apply_background(widget: tk.Misc, palette: dict[str, str]) -> None:
    bg = palette["COL_BG"]
    try:
        widget.configure(bg=bg)
    except tk.TclError:
        pass
    for child in widget.winfo_children():
        _apply_background(child, palette)


def apply_theme(root: tk.Misc, name: str = "modern") -> None:
    """Apply the selected theme to *root* and refresh shared widgets."""

    resolved = set_theme(name)
    palette = _THEMES[resolved]
    _apply_background(root, palette)
    _configure_styles(palette)

    # Allow widgets to refresh cached constants without hard imports at module
    # import time.
    try:  # pragma: no cover - best effort only
        widget_mod = importlib.import_module("bascula.ui.widgets")
        if hasattr(widget_mod, "refresh_theme_cache"):
            widget_mod.refresh_theme_cache()
    except Exception:
        pass


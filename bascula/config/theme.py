"""Simple theme helpers for the kiosk UI."""
from __future__ import annotations

from tkinter import ttk
import tkinter as tk

_THEMES = {
    "retro": {
        "BG": "#000000",
        "TEXT": "#00FF66",
        "ACCENT": "#00FF99",
        "BORDER": "#00FF66",
    },
    "modern": {
        "BG": "#0a0e1a",
        "TEXT": "#f0f4f8",
        "ACCENT": "#00d4aa",
        "BORDER": "#2a3142",
    },
}

_current_theme = "retro"


def colors() -> dict[str, str]:
    """Return a copy of the active palette."""
    return dict(_THEMES[_current_theme])


def _configure_styles(palette: dict[str, str]) -> None:
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure("TFrame", background=palette["BG"], bordercolor=palette["BORDER"])
    style.configure(
        "TLabel",
        background=palette["BG"],
        foreground=palette["TEXT"],
    )
    style.configure(
        "TButton",
        background=palette["BORDER"],
        foreground=palette["BG"],
        bordercolor=palette["BORDER"],
        focusthickness=1,
    )
    style.map(
        "TButton",
        background=[("active", palette["ACCENT"])],
        foreground=[("active", palette["BG"])],
    )


def _apply_background(widget: tk.Misc, background: str) -> None:
    try:
        widget.configure(bg=background)
    except tk.TclError:
        pass
    for child in widget.winfo_children():
        _apply_background(child, background)


def apply_theme(root: tk.Misc, name: str = "retro") -> None:
    """Apply one of the predefined color palettes to *root*."""
    global _current_theme
    if name not in _THEMES:
        name = "retro"
    _current_theme = name
    palette = _THEMES[name]
    _apply_background(root, palette["BG"])
    _configure_styles(palette)

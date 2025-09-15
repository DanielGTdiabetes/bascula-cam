from __future__ import annotations

"""Minimal theme system with only two well integrated themes."""

from dataclasses import dataclass
from typing import Dict, Optional
import tkinter as tk
from tkinter import ttk

@dataclass
class Theme:
    name: str
    display_name: str
    palette: Dict[str, str]

# Palettes ---------------------------------------------------------------

def _modern_palette() -> Dict[str, str]:
    return {
        'COL_BG': '#0a0e1a',
        'COL_CARD': '#141823',
        'COL_CARD_HOVER': '#1a1f2e',
        'COL_TEXT': '#f0f4f8',
        'COL_MUTED': '#8892a0',
        'COL_ACCENT': '#00d4aa',
        'COL_ACCENT_LIGHT': '#00ffcc',
        'COL_SUCCESS': '#00d4aa',
        'COL_WARN': '#ffa500',
        'COL_DANGER': '#ff6b6b',
        'COL_BORDER': '#2a3142',
    }

def _retro_palette() -> Dict[str, str]:
    return {
        'COL_BG': '#000000',
        'COL_CARD': '#000000',
        'COL_CARD_HOVER': '#001a0c',
        'COL_TEXT': '#00ff66',
        'COL_MUTED': '#00cc55',
        'COL_ACCENT': '#00ff99',
        'COL_ACCENT_LIGHT': '#22ffbb',
        'COL_SUCCESS': '#44ff88',
        'COL_WARN': '#ffee33',
        'COL_DANGER': '#ff3366',
        'COL_BORDER': '#00ff66',
    }

THEMES: Dict[str, Theme] = {
    'modern': Theme('modern', 'Normal / Moderno', _modern_palette()),
    'retro': Theme('retro', 'Retro (terminal)', _retro_palette()),
}

_current_theme: Theme = THEMES['modern']

# Helper API ------------------------------------------------------------

COLORS = THEMES['modern'].palette.copy()

def get_current_colors() -> Dict[str, str]:
    return COLORS

def set_theme(name: str) -> None:
    global _current_theme, COLORS
    if name not in THEMES:
        return
    _current_theme = THEMES[name]
    COLORS.update(_current_theme.palette)
    update_color_constants()

def apply_theme(root: tk.Misc, name: str) -> None:
    set_theme(name)
    try:
        root.configure(bg=COLORS['COL_BG'])
    except Exception:
        pass
    _restyle_widgets(root)
    _style_ttk()

# propagate palette to widget module -----------------------------------

def update_color_constants() -> None:
    try:
        from bascula.ui import widgets
        for k, v in COLORS.items():
            setattr(widgets, k, v)
    except Exception:
        pass

# generic restyling -----------------------------------------------------

def _restyle_widgets(widget: tk.Misc) -> None:
    for child in widget.winfo_children():
        try:
            if isinstance(child, (tk.Frame, tk.Label)):
                child.configure(bg=COLORS['COL_CARD'], fg=COLORS['COL_TEXT'])
            elif isinstance(child, tk.Button):
                child.configure(bg=COLORS['COL_ACCENT'], fg=COLORS['COL_TEXT'],
                                activebackground=COLORS['COL_ACCENT_LIGHT'])
        except Exception:
            pass
        _restyle_widgets(child)


def _style_ttk() -> None:
    try:
        style = ttk.Style()
        style.theme_use('default')
        style.configure('TNotebook', background=COLORS['COL_BG'], borderwidth=0)
        style.configure('TNotebook.Tab', background=COLORS['COL_CARD'], foreground=COLORS['COL_TEXT'])
        style.map('TNotebook.Tab', background=[('selected', COLORS['COL_ACCENT'])])
        style.configure('Vertical.TScrollbar', troughcolor=COLORS['COL_CARD'], background=COLORS['COL_ACCENT'], bordercolor=COLORS['COL_BORDER'], arrowcolor=COLORS['COL_TEXT'])
        style.configure('Horizontal.TScrollbar', troughcolor=COLORS['COL_CARD'], background=COLORS['COL_ACCENT'], bordercolor=COLORS['COL_BORDER'], arrowcolor=COLORS['COL_TEXT'])
    except Exception:
        pass

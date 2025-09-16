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
        'COL_SHADOW': '#000000',
        'COL_GRADIENT_START': '#141823',
        'COL_GRADIENT_END': '#0a0e1a',
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
        'COL_SHADOW': '#003311',
        'COL_GRADIENT_START': '#000000',
        'COL_GRADIENT_END': '#001100',
    }

def _light_palette() -> Dict[str, str]:
    return {
        'COL_BG': '#f8fafc',
        'COL_CARD': '#ffffff',
        'COL_CARD_HOVER': '#f1f5f9',
        'COL_TEXT': '#1e293b',
        'COL_MUTED': '#64748b',
        'COL_ACCENT': '#3b82f6',
        'COL_ACCENT_LIGHT': '#60a5fa',
        'COL_SUCCESS': '#10b981',
        'COL_WARN': '#f59e0b',
        'COL_DANGER': '#ef4444',
        'COL_BORDER': '#e2e8f0',
        'COL_SHADOW': '#00000020',
        'COL_GRADIENT_START': '#ffffff',
        'COL_GRADIENT_END': '#f8fafc',
    }

def _high_contrast_palette() -> Dict[str, str]:
    return {
        'COL_BG': '#000000',
        'COL_CARD': '#000000',
        'COL_CARD_HOVER': '#333333',
        'COL_TEXT': '#ffffff',
        'COL_MUTED': '#cccccc',
        'COL_ACCENT': '#ffff00',
        'COL_ACCENT_LIGHT': '#ffff99',
        'COL_SUCCESS': '#00ff00',
        'COL_WARN': '#ff8800',
        'COL_DANGER': '#ff0000',
        'COL_BORDER': '#ffffff',
        'COL_SHADOW': '#ffffff40',
        'COL_GRADIENT_START': '#000000',
        'COL_GRADIENT_END': '#222222',
    }

def _colorful_palette() -> Dict[str, str]:
    return {
        'COL_BG': '#1a1b3a',
        'COL_CARD': '#2d2f5f',
        'COL_CARD_HOVER': '#3a3d7a',
        'COL_TEXT': '#ffffff',
        'COL_MUTED': '#b8bcc8',
        'COL_ACCENT': '#ff6b9d',
        'COL_ACCENT_LIGHT': '#ff8fb3',
        'COL_SUCCESS': '#4ecdc4',
        'COL_WARN': '#ffe66d',
        'COL_DANGER': '#ff6b6b',
        'COL_BORDER': '#4a4d7a',
        'COL_SHADOW': '#00000060',
        'COL_GRADIENT_START': '#2d2f5f',
        'COL_GRADIENT_END': '#1a1b3a',
    }

def _ocean_palette() -> Dict[str, str]:
    return {
        'COL_BG': '#0f172a',
        'COL_CARD': '#1e293b',
        'COL_CARD_HOVER': '#334155',
        'COL_TEXT': '#f1f5f9',
        'COL_MUTED': '#94a3b8',
        'COL_ACCENT': '#0ea5e9',
        'COL_ACCENT_LIGHT': '#38bdf8',
        'COL_SUCCESS': '#06b6d4',
        'COL_WARN': '#f97316',
        'COL_DANGER': '#e11d48',
        'COL_BORDER': '#475569',
        'COL_SHADOW': '#00000080',
        'COL_GRADIENT_START': '#1e293b',
        'COL_GRADIENT_END': '#0f172a',
    }

THEMES: Dict[str, Theme] = {
    'modern': Theme('modern', 'Normal / Moderno', _modern_palette()),
    'retro': Theme('retro', 'Retro (terminal)', _retro_palette()),
    'light': Theme('light', 'Claro / Light', _light_palette()),
    'high_contrast': Theme('high_contrast', 'Alto Contraste', _high_contrast_palette()),
    'colorful': Theme('colorful', 'Colorido / Colorful', _colorful_palette()),
    'ocean': Theme('ocean', 'Océano / Ocean', _ocean_palette()),
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

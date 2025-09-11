"""
Minimal theme manager to support runtime theme switching.

Exports:
- THEMES: mapping of theme_name -> Theme
- get_theme_manager(): singleton ThemeManager
- apply_theme(root, theme_name): convenience to set/apply
- update_color_constants(): propagate palette to bascula.ui.widgets globals
- get_current_colors(): current palette dict

Notes:
- Focuses on updating color constants used across the UI. Widgets
  pick up new colors when screens are recreated.
- Provides optional scanlines overlay helpers compatible with the UI calls.
"""
from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class Theme:
    name: str
    display_name: str
    palette: Dict[str, str]
    scanlines: bool = False
    glow_effect: bool = False


def _dark_modern_palette() -> Dict[str, str]:
    # Matches defaults in bascula.ui.widgets
    return {
        'COL_BG': "#0a0e1a",
        'COL_CARD': "#141823",
        'COL_CARD_HOVER': "#1a1f2e",
        'COL_TEXT': "#f0f4f8",
        'COL_MUTED': "#8892a0",
        'COL_ACCENT': "#00d4aa",
        'COL_ACCENT_LIGHT': "#00ffcc",
        'COL_SUCCESS': "#00d4aa",
        'COL_WARN': "#ffa500",
        'COL_DANGER': "#ff6b6b",
        'COL_BORDER': "#2a3142",
    }


def _retro_palette() -> Dict[str, str]:
    # Inspired by config.theme CRT palette
    return {
        'COL_BG': "#000000",
        'COL_CARD': "#000000",
        'COL_CARD_HOVER': "#001a0c",
        'COL_TEXT': "#00ff66",
        'COL_MUTED': "#00cc55",
        'COL_ACCENT': "#00ff99",
        'COL_ACCENT_LIGHT': "#22ffbb",
        'COL_SUCCESS': "#44ff88",
        'COL_WARN': "#ffee33",
        'COL_DANGER': "#ff3366",
        'COL_BORDER': "#00ff66",
    }


def _synthwave_palette() -> Dict[str, str]:
    return {
        'COL_BG': "#0b0b2b",
        'COL_CARD': "#13133d",
        'COL_CARD_HOVER': "#1c1c56",
        'COL_TEXT': "#e5e7ff",
        'COL_MUTED': "#a3a6d6",
        'COL_ACCENT': "#ff00c3",
        'COL_ACCENT_LIGHT': "#00eaff",
        'COL_SUCCESS': "#00ffa6",
        'COL_WARN': "#ffd166",
        'COL_DANGER': "#ff3366",
        'COL_BORDER': "#2a2a6e",
    }

def _cyberpunk_palette() -> Dict[str, str]:
    return {
        'COL_BG': "#0a0a0a",
        'COL_CARD': "#0f0f0f",
        'COL_CARD_HOVER': "#161616",
        'COL_TEXT': "#ffe600",
        'COL_MUTED': "#ff9bd1",
        'COL_ACCENT': "#ffce00",
        'COL_ACCENT_LIGHT': "#ffde4d",
        'COL_SUCCESS': "#00ffa6",
        'COL_WARN': "#ffea00",
        'COL_DANGER': "#ff2a6d",
        'COL_BORDER': "#2d2d2d",
    }

def _amber_palette() -> Dict[str, str]:
    return {
        'COL_BG': "#0b0b0b",
        'COL_CARD': "#0f0f0f",
        'COL_CARD_HOVER': "#1a1a1a",
        'COL_TEXT': "#ffbf00",
        'COL_MUTED': "#d4a017",
        'COL_ACCENT': "#ffbf00",
        'COL_ACCENT_LIGHT': "#ffd24d",
        'COL_SUCCESS': "#c3ff00",
        'COL_WARN': "#ffbf00",
        'COL_DANGER': "#ff6b35",
        'COL_BORDER': "#3a3a3a",
    }

def _matrix_palette() -> Dict[str, str]:
    return {
        'COL_BG': "#000000",
        'COL_CARD': "#000000",
        'COL_CARD_HOVER': "#0a1f0a",
        'COL_TEXT': "#00ff41",
        'COL_MUTED': "#00cc33",
        'COL_ACCENT': "#00ff41",
        'COL_ACCENT_LIGHT': "#22ff66",
        'COL_SUCCESS': "#44ff88",
        'COL_WARN': "#ffee33",
        'COL_DANGER': "#ff3366",
        'COL_BORDER': "#00ff41",
    }

def _vaporwave_palette() -> Dict[str, str]:
    return {
        'COL_BG': "#221c35",
        'COL_CARD': "#2a2342",
        'COL_CARD_HOVER': "#342d52",
        'COL_TEXT': "#ffeeff",
        'COL_MUTED': "#d6b3ff",
        'COL_ACCENT': "#ff77aa",
        'COL_ACCENT_LIGHT': "#b2a1ff",
        'COL_SUCCESS': "#a1ffea",
        'COL_WARN': "#ffd1a1",
        'COL_DANGER': "#ff6699",
        'COL_BORDER': "#473a75",
    }

def _light_palette() -> Dict[str, str]:
    return {
        'COL_BG': "#f7f7fb",
        'COL_CARD': "#ffffff",
        'COL_CARD_HOVER': "#f0f3f9",
        'COL_TEXT': "#111827",
        'COL_MUTED': "#6b7280",
        'COL_ACCENT': "#2563eb",
        'COL_ACCENT_LIGHT': "#60a5fa",
        'COL_SUCCESS': "#16a34a",
        'COL_WARN': "#d97706",
        'COL_DANGER': "#dc2626",
        'COL_BORDER': "#e5e7eb",
    }

THEMES: Dict[str, Theme] = {
    'dark_modern': Theme('dark_modern', '🌙 Dark Modern', _dark_modern_palette()),
    'light': Theme('light', '☀️ Light Mode', _light_palette()),
    'retro': Theme('retro', '🖥️ CRT Verde Retro', _retro_palette(), scanlines=False, glow_effect=True),
    'crt': Theme('crt', '🖥️ CRT Verde Retro', _retro_palette(), scanlines=False, glow_effect=True),
    'synthwave': Theme('synthwave', '🌆 Synthwave Neón', _synthwave_palette(), glow_effect=True),
    'cyberpunk': Theme('cyberpunk', '🌃 Cyberpunk 2077', _cyberpunk_palette(), glow_effect=True),
    'amber': Theme('amber', '📟 Terminal Ámbar', _amber_palette()),
    'matrix': Theme('matrix', '💊 Matrix', _matrix_palette(), scanlines=True),
    'vaporwave': Theme('vaporwave', '🌴 Vaporwave', _vaporwave_palette(), glow_effect=True),
}


class ThemeManager:
    def __init__(self) -> None:
        self.current_theme_name: str = 'dark_modern'
        self.current_theme: Theme = THEMES[self.current_theme_name]
        self._scan_overlay: Optional[tk.Canvas] = None

    def set_theme(self, name: str) -> bool:
        if name not in THEMES:
            return False
        self.current_theme_name = name
        self.current_theme = THEMES[name]
        return True

    def apply_to_root(self, root: tk.Misc) -> None:
        # Update palette constants first
        update_color_constants()
        try:
            root.configure(bg=self.current_theme.palette['COL_BG'])
        except Exception:
            pass

    # Scanlines helpers (used by UI)
    def _apply_scanlines(self, root: tk.Misc) -> None:
        self._remove_scanlines()
        try:
            overlay = tk.Canvas(root, highlightthickness=0, bd=0, bg=self.current_theme.palette['COL_BG'])
            overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
            h = 2
            def draw():
                try:
                    overlay.delete("all")
                    w = overlay.winfo_width(); height = overlay.winfo_height()
                    for y in range(0, height, h*2):
                        overlay.create_rectangle(0, y, w, y+h, outline="", fill="#000000")
                    overlay.after(1000, draw)
                except Exception:
                    pass
            overlay.bind("<Configure>", lambda e: draw())
            overlay.lower()  # stay below to not intercept events
            self._scan_overlay = overlay
        except Exception:
            self._scan_overlay = None

    def _remove_scanlines(self) -> None:
        try:
            if self._scan_overlay is not None:
                self._scan_overlay.destroy()
        except Exception:
            pass
        self._scan_overlay = None

    # Optional stub for glow effect (no-op by default)
    def apply_glow_effect(self, widget: tk.Widget) -> None:
        # Soft glow simulation: pulsate foreground to accent color
        try:
            pal = self.current_theme.palette
            base = pal['COL_TEXT']
            acc = pal['COL_ACCENT']
            state = {'on': True}

            def tick():
                try:
                    widget.configure(fg=(acc if state['on'] else base))
                    state['on'] = not state['on']
                    widget.after(900, tick)
                except Exception:
                    pass
            tick()
        except Exception:
            pass


_manager: Optional[ThemeManager] = None


def get_theme_manager() -> ThemeManager:
    global _manager
    if _manager is None:
        _manager = ThemeManager()
    return _manager


def apply_theme(root: tk.Misc, name: str) -> None:
    tm = get_theme_manager()
    if tm.set_theme(name):
        tm.apply_to_root(root)
        update_color_constants()

def initialize_theme(root: tk.Misc, cfg: dict) -> None:
    name = cfg.get('ui_theme', 'dark_modern')
    apply_theme(root, name)
    tm = get_theme_manager()
    if cfg.get('theme_scanlines', False):
        tm._apply_scanlines(root)


def update_color_constants() -> None:
    """Propagate current theme palette into bascula.ui.widgets module globals."""
    try:
        from bascula.ui import widgets as w
        pal = get_theme_manager().current_theme.palette
        # Assign globals used across the UI
        w.COL_BG = pal['COL_BG']
        w.COL_CARD = pal['COL_CARD']
        w.COL_CARD_HOVER = pal['COL_CARD_HOVER']
        w.COL_TEXT = pal['COL_TEXT']
        w.COL_MUTED = pal['COL_MUTED']
        w.COL_ACCENT = pal['COL_ACCENT']
        w.COL_ACCENT_LIGHT = pal['COL_ACCENT_LIGHT']
        w.COL_SUCCESS = pal['COL_SUCCESS']
        w.COL_WARN = pal['COL_WARN']
        w.COL_DANGER = pal['COL_DANGER']
        w.COL_BORDER = pal['COL_BORDER']
    except Exception:
        pass


def get_current_colors() -> Dict[str, str]:
    return dict(get_theme_manager().current_theme.palette)

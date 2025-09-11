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


THEMES: Dict[str, Theme] = {
    'dark_modern': Theme('dark_modern', 'Dark Modern', _dark_modern_palette()),
    'retro': Theme('retro', 'Retro Verde', _retro_palette(), scanlines=False),
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
        # Implement visual glow if desired; for now, this is a no-op.
        return


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


"""Custom holographic ttk theme utilities for the Báscula UI."""
from __future__ import annotations

import tkinter as tk
from tkinter import Canvas, Misc, ttk
from typing import Optional

COLOR_BG = "#0A0A0A"
COLOR_PRIMARY = "#00E5FF"
COLOR_ACCENT = "#FF00DC"
COLOR_TEXT = "#FFFFFF"
COLOR_MUTED = "#7F7F7F"
GRID_COLOR = "#05363D"

FONT_UI = ("DejaVu Sans", 12)
FONT_UI_BOLD = ("DejaVu Sans", 12, "bold")
FONT_DIGITS = ("DejaVu Sans Mono", 54, "bold")


def _safe_style(root: Misc) -> ttk.Style:
    try:
        return ttk.Style(root)
    except Exception:
        return ttk.Style()


def apply_holo_theme(root: Optional[Misc] = None) -> None:
    """Register and apply the holographic ttk theme."""

    style = _safe_style(root)
    if "holo" not in style.theme_names():
        settings = {
            "TFrame": {
                "configure": {
                    "background": COLOR_BG,
                }
            },
            "TLabelframe": {
                "configure": {
                    "background": COLOR_BG,
                    "foreground": COLOR_TEXT,
                    "bordercolor": COLOR_PRIMARY,
                }
            },
            "TLabelframe.Label": {
                "configure": {
                    "background": COLOR_BG,
                    "foreground": COLOR_TEXT,
                    "font": FONT_UI_BOLD,
                }
            },
            "TLabel": {
                "configure": {
                    "background": COLOR_BG,
                    "foreground": COLOR_TEXT,
                    "font": FONT_UI,
                }
            },
            "TButton": {
                "configure": {
                    "background": COLOR_BG,
                    "foreground": COLOR_TEXT,
                    "font": FONT_UI_BOLD,
                    "padding": (16, 8),
                    "borderwidth": 1,
                    "focuscolor": COLOR_ACCENT,
                    "bordercolor": COLOR_PRIMARY,
                    "relief": "flat",
                },
                "map": {
                    "foreground": [
                        ("disabled", "#555555"),
                        ("pressed", COLOR_BG),
                        ("active", COLOR_TEXT),
                    ],
                    "background": [
                        ("pressed", COLOR_ACCENT),
                        ("active", "#141414"),
                    ],
                    "bordercolor": [
                        ("pressed", COLOR_ACCENT),
                        ("active", COLOR_ACCENT),
                    ],
                },
            },
            "Holo.Circular.TButton": {
                "configure": {
                    "background": COLOR_BG,
                    "foreground": COLOR_TEXT,
                    "font": FONT_UI_BOLD,
                    "padding": (18, 12),
                    "borderwidth": 2,
                    "relief": "flat",
                    "focuscolor": COLOR_ACCENT,
                    "bordercolor": COLOR_PRIMARY,
                },
                "map": {
                    "foreground": [
                        ("pressed", COLOR_BG),
                        ("active", COLOR_TEXT),
                    ],
                    "background": [
                        ("pressed", COLOR_ACCENT),
                        ("active", "#141414"),
                    ],
                    "bordercolor": [
                        ("pressed", COLOR_ACCENT),
                        ("active", COLOR_ACCENT),
                    ],
                },
            },
            "TNotebook": {
                "configure": {
                    "background": COLOR_BG,
                    "borderwidth": 0,
                    "tabmargins": (16, 8, 16, 0),
                    "padding": 4,
                }
            },
            "TNotebook.Tab": {
                "configure": {
                    "font": FONT_UI_BOLD,
                    "foreground": COLOR_PRIMARY,
                    "background": COLOR_BG,
                    "padding": (20, 10),
                },
                "map": {
                    "foreground": [("selected", COLOR_ACCENT)],
                    "background": [("selected", "#141414")],
                    "bordercolor": [
                        ("selected", COLOR_ACCENT),
                        ("!selected", COLOR_PRIMARY),
                    ],
                },
            },
            "TEntry": {
                "configure": {
                    "fieldbackground": "#141414",
                    "foreground": COLOR_TEXT,
                    "bordercolor": COLOR_PRIMARY,
                    "lightcolor": COLOR_PRIMARY,
                    "darkcolor": COLOR_PRIMARY,
                    "insertcolor": COLOR_ACCENT,
                    "padding": 6,
                    "relief": "flat",
                },
                "map": {
                    "bordercolor": [("focus", COLOR_ACCENT)],
                    "lightcolor": [("focus", COLOR_ACCENT)],
                    "darkcolor": [("focus", COLOR_ACCENT)],
                },
            },
            "Horizontal.TProgressbar": {
                "configure": {
                    "background": COLOR_PRIMARY,
                    "troughcolor": "#101010",
                    "bordercolor": COLOR_BG,
                    "lightcolor": COLOR_PRIMARY,
                    "darkcolor": COLOR_PRIMARY,
                },
            },
            "Vertical.TScrollbar": {
                "configure": {
                    "gripcount": 0,
                    "background": "#141414",
                    "troughcolor": "#101010",
                    "bordercolor": COLOR_BG,
                    "lightcolor": COLOR_PRIMARY,
                    "darkcolor": COLOR_PRIMARY,
                    "arrowcolor": COLOR_PRIMARY,
                },
                "map": {
                    "background": [("active", COLOR_ACCENT)],
                    "arrowcolor": [("active", COLOR_ACCENT)],
                },
            },
        }
        style.theme_create("holo", parent="clam", settings=settings)

    style.theme_use("holo")

    root_widget = root or style.master
    if isinstance(root_widget, tk.Tk) or isinstance(root_widget, tk.Toplevel):
        try:
            root_widget.configure(bg=COLOR_BG)
        except Exception:
            pass

    if root_widget is not None:
        try:
            root_widget.option_add("*Font", FONT_UI)
            root_widget.option_add("*Label.Font", FONT_UI)
            root_widget.option_add("*Button.Font", FONT_UI_BOLD)
            root_widget.option_add("*Entry.Font", FONT_UI)
            root_widget.option_add("*foreground", COLOR_TEXT)
        except Exception:
            pass


def paint_grid_background(target: Misc, *, spacing: int = 40) -> Optional[Canvas]:
    """Paint a subtle cyan grid behind the given widget."""

    try:
        canvas = Canvas(target, bg=COLOR_BG, highlightthickness=0, bd=0)
    except Exception:
        return None

    canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
    canvas.lower()

    def _draw(_event=None) -> None:
        try:
            width = max(1, target.winfo_width())
            height = max(1, target.winfo_height())
        except Exception:
            return
        canvas.delete("grid")
        for x in range(0, width, spacing):
            canvas.create_line(x, 0, x, height, fill=GRID_COLOR, width=1, tags="grid")
        for y in range(0, height, spacing):
            canvas.create_line(0, y, width, y, fill=GRID_COLOR, width=1, tags="grid")

    try:
        target.bind("<Configure>", _draw, add=True)
    except Exception:
        pass
    _draw()
    return canvas


def neon_border(widget: Misc, *, padding: int = 6, radius: int = 18, color: str = COLOR_PRIMARY) -> Optional[Canvas]:
    """Draw a neon-style rounded border behind the provided widget."""

    master = widget.master
    if master is None:
        return None

    try:
        border_canvas = Canvas(master, highlightthickness=0, bd=0, bg=COLOR_BG)
    except Exception:
        return None

    def _rounded_rect(canvas: Canvas, x1: int, y1: int, x2: int, y2: int, rad: int) -> None:
        rad = max(4, min(rad, int(min(x2 - x1, y2 - y1) / 2)))
        points = [
            x1 + rad,
            y1,
            x2 - rad,
            y1,
            x2,
            y1,
            x2,
            y1 + rad,
            x2,
            y2 - rad,
            x2,
            y2,
            x2 - rad,
            y2,
            x1 + rad,
            y2,
            x1,
            y2,
            x1,
            y2 - rad,
            x1,
            y1 + rad,
            x1,
            y1,
            x1 + rad,
            y1,
        ]
        canvas.create_polygon(
            points,
            smooth=True,
            outline=color,
            fill="",
            width=2,
            tags="border",
        )

    def _update(_event=None) -> None:
        try:
            x = widget.winfo_x()
            y = widget.winfo_y()
            w = widget.winfo_width()
            h = widget.winfo_height()
        except Exception:
            return
        if w <= 1 and h <= 1:
            widget.after(50, _update)
            return
        border_canvas.place(x=max(0, x - padding), y=max(0, y - padding), width=w + padding * 2, height=h + padding * 2)
        border_canvas.lower(widget)
        border_canvas.delete("border")
        _rounded_rect(border_canvas, 2, 2, max(4, w + padding * 2 - 2), max(4, h + padding * 2 - 2), radius)

    try:
        widget.bind("<Configure>", _update, add=True)
        master.bind("<Configure>", _update, add=True)
    except Exception:
        pass
    widget.after(10, _update)
    return border_canvas


__all__ = [
    "apply_holo_theme",
    "paint_grid_background",
    "neon_border",
    "FONT_UI",
    "FONT_UI_BOLD",
    "FONT_DIGITS",
    "COLOR_BG",
    "COLOR_PRIMARY",
    "COLOR_ACCENT",
    "COLOR_TEXT",
    "COLOR_MUTED",
]

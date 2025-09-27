"""Holographic ttk theme helpers for the Báscula UI."""
from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import Canvas, Misc, ttk
from tkinter import font as tkfont
from typing import Iterable, Optional, Sequence

__all__ = [
    "apply_holo_theme",
    "paint_grid_background",
    "neon_border",
    "COLOR_BG",
    "COLOR_GRID",
    "COLOR_PRIMARY",
    "COLOR_ACCENT",
    "COLOR_SURFACE",
    "COLOR_TEXT",
    "PALETTE",
    "FONT_BODY",
    "FONT_BODY_BOLD",
    "FONT_HEADER",
    "FONT_SUBHEADER",
    "FONT_MONO_LG",
    "FONT_BUTTON",
    "FONT_UI",
    "FONT_UI_BOLD",
    "FONT_DIGITS",
]


COLOR_BG = "#071019"
COLOR_GRID = "#00cbd6"
COLOR_PRIMARY = "#18e6ff"
COLOR_ACCENT = "#ff2db2"
COLOR_SURFACE = "#0e2230"
COLOR_SURFACE_HI = "#143447"
COLOR_TEXT = "#d8f6ff"
COLOR_TEXT_MUTED = "#93b4c4"
COLOR_OUTLINE = "#114052"

PALETTE = {
    "bg": COLOR_BG,
    "surface": COLOR_SURFACE,
    "surface_hi": COLOR_SURFACE_HI,
    "text": COLOR_TEXT,
    "text_muted": COLOR_TEXT_MUTED,
    "primary": COLOR_PRIMARY,
    "accent": COLOR_ACCENT,
    "outline": COLOR_OUTLINE,
}


@dataclass(frozen=True)
class _FontSpec:
    family_preferences: Sequence[str]
    fallbacks: Sequence[str]
    size: int
    weight: str | None = None

    def resolve(self, available: Iterable[str]) -> tuple[str, int] | tuple[str, int, str]:
        family = _choose_font_family(self.family_preferences, self.fallbacks, available)
        if self.weight and self.weight.lower() != "normal":
            return (family, self.size, self.weight)
        return (family, self.size)


def _choose_font_family(
    preferred: Sequence[str],
    fallbacks: Sequence[str],
    available: Iterable[str] | None = None,
) -> str:
    """Return the first available font family from the provided sequences."""

    if available is None:
        try:
            available = tkfont.families()
        except Exception:
            available = []
    available_set = {family.lower() for family in available}

    for family in preferred:
        if family.lower() in available_set:
            return family
    for family in fallbacks:
        if family.lower() in available_set:
            return family
    return fallbacks[-1] if fallbacks else preferred[0]


def _get_font_specs(style: ttk.Style) -> dict[str, tuple[str, int] | tuple[str, int, str]]:
    try:
        available = tkfont.families(style.master)
    except Exception:
        available = []

    specs = {
        "body": _FontSpec(("Oxanium",), ("DejaVu Sans", "TkDefaultFont"), 12).resolve(available),
        "body_bold": _FontSpec(("Oxanium",), ("DejaVu Sans", "TkDefaultFont"), 12, "bold").resolve(available),
        "header": _FontSpec(("Oxanium",), ("DejaVu Sans", "TkDefaultFont"), 24, "bold").resolve(available),
        "subheader": _FontSpec(("Oxanium",), ("DejaVu Sans", "TkDefaultFont"), 16).resolve(available),
        "button": _FontSpec(("Oxanium",), ("DejaVu Sans", "TkDefaultFont"), 13, "bold").resolve(
            available
        ),
        "mono_lg": _FontSpec(
            ("Share Tech Mono",),
            ("DejaVu Sans Mono", "Monospace", "TkFixedFont"),
            36,
            "bold",
        ).resolve(available),
    }
    return specs


FONT_BODY: tuple[str, int] | tuple[str, int, str] = ("DejaVu Sans", 12)
FONT_BODY_BOLD: tuple[str, int] | tuple[str, int, str] = ("DejaVu Sans", 12, "bold")
FONT_HEADER: tuple[str, int] | tuple[str, int, str] = ("DejaVu Sans", 24, "bold")
FONT_SUBHEADER: tuple[str, int] | tuple[str, int, str] = ("DejaVu Sans", 16)
FONT_MONO_LG: tuple[str, int] | tuple[str, int, str] = ("DejaVu Sans Mono", 36, "bold")
FONT_BUTTON: tuple[str, int] | tuple[str, int, str] = ("DejaVu Sans", 12, "bold")

# Backwards compatibility aliases for legacy imports
FONT_UI = FONT_BODY
FONT_UI_BOLD = FONT_BODY_BOLD
FONT_DIGITS = FONT_MONO_LG


def apply_holo_theme(root: Optional[Misc] = None) -> None:
    """Register and activate the holographic theme for ttk widgets."""

    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    fonts = _get_font_specs(style)
    global FONT_BODY, FONT_BODY_BOLD, FONT_HEADER, FONT_SUBHEADER, FONT_MONO_LG, FONT_BUTTON
    global FONT_UI, FONT_UI_BOLD, FONT_DIGITS
    FONT_BODY = fonts["body"]
    FONT_BODY_BOLD = fonts["body_bold"]
    FONT_HEADER = fonts["header"]
    FONT_SUBHEADER = fonts["subheader"]
    FONT_MONO_LG = fonts["mono_lg"]
    FONT_BUTTON = fonts.get("button", FONT_BODY_BOLD)
    FONT_UI = FONT_BODY
    FONT_UI_BOLD = FONT_BODY_BOLD
    FONT_DIGITS = FONT_MONO_LG

    style.configure("TFrame", background=COLOR_SURFACE)
    style.configure(
        "TLabel",
        background=COLOR_SURFACE,
        foreground=COLOR_TEXT,
        font=FONT_BODY,
    )
    style.configure(
        "Header.TLabel",
        background=COLOR_SURFACE,
        foreground=COLOR_PRIMARY,
        font=FONT_HEADER,
    )
    style.configure(
        "Subheader.TLabel",
        background=COLOR_SURFACE,
        foreground=COLOR_ACCENT,
        font=FONT_SUBHEADER,
    )

    style.configure(
        "TButton",
        background=COLOR_SURFACE,
        foreground=COLOR_TEXT,
        font=FONT_BODY_BOLD,
        padding=(12, 8),
        borderwidth=1,
        focusthickness=2,
        focuscolor=COLOR_PRIMARY,
        relief="flat",
    )
    style.map(
        "TButton",
        background=[("active", COLOR_BG), ("pressed", COLOR_ACCENT)],
        foreground=[("active", COLOR_TEXT), ("pressed", COLOR_TEXT)],
        bordercolor=[("focus", COLOR_PRIMARY)],
    )

    style.configure(
        "Toolbar.TFrame",
        background=PALETTE["bg"],
        borderwidth=0,
        relief="flat",
        padding=(24, 12, 24, 8),
    )
    style.configure(
        "Toolbar.TLabel",
        background=PALETTE["bg"],
        foreground=PALETTE["text_muted"],
        font=FONT_BODY,
    )
    style.configure(
        "Toolbar.Separator.TFrame",
        background=PALETTE["outline"],
        borderwidth=0,
        height=1,
        relief="flat",
    )
    style.configure(
        "Toolbutton.TButton",
        background=PALETTE["bg"],
        foreground=PALETTE["text_muted"],
        borderwidth=0,
        focusthickness=0,
        relief="flat",
        padding=(10, 8),
        font=FONT_BUTTON,
    )
    style.map(
        "Toolbutton.TButton",
        foreground=[("active", PALETTE["primary"]), ("pressed", PALETTE["accent"])],
        background=[("active", PALETTE["surface_hi"]), ("pressed", PALETTE["surface"])],
        bordercolor=[("focus", PALETTE["primary"])],
    )

    style.configure(
        "Primary.TButton",
        background=COLOR_PRIMARY,
        foreground=COLOR_BG,
        padding=(14, 10),
        font=FONT_BODY_BOLD,
        relief="flat",
    )
    style.map(
        "Primary.TButton",
        background=[("active", COLOR_ACCENT), ("pressed", COLOR_ACCENT)],
        foreground=[("active", COLOR_BG), ("pressed", COLOR_BG)],
    )

    style.configure(
        "Accent.TButton",
        background=COLOR_ACCENT,
        foreground=COLOR_BG,
        padding=(14, 10),
        font=FONT_BODY_BOLD,
        relief="flat",
    )
    style.map(
        "Accent.TButton",
        background=[("active", COLOR_PRIMARY), ("pressed", COLOR_PRIMARY)],
        foreground=[("active", COLOR_BG), ("pressed", COLOR_BG)],
    )

    style.configure(
        "TEntry",
        fieldbackground=COLOR_BG,
        background=COLOR_BG,
        foreground=COLOR_TEXT,
        insertcolor=COLOR_ACCENT,
        bordercolor=COLOR_PRIMARY,
        lightcolor=COLOR_PRIMARY,
        darkcolor=COLOR_PRIMARY,
        padding=8,
        relief="flat",
        font=FONT_BODY,
    )
    style.map(
        "TEntry",
        bordercolor=[("focus", COLOR_ACCENT)],
        lightcolor=[("focus", COLOR_ACCENT)],
        darkcolor=[("focus", COLOR_ACCENT)],
    )

    style.configure(
        "TNotebook",
        background=COLOR_BG,
        borderwidth=0,
        tabmargins=(16, 8, 16, 0),
    )
    style.configure(
        "TNotebook.Tab",
        background=COLOR_SURFACE,
        foreground=COLOR_TEXT,
        padding=(18, 10),
        font=FONT_BODY_BOLD,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", COLOR_BG)],
        foreground=[("selected", COLOR_PRIMARY)],
    )

    style.configure(
        "Treeview",
        background=COLOR_SURFACE,
        fieldbackground=COLOR_SURFACE,
        foreground=COLOR_TEXT,
        rowheight=32,
        font=FONT_BODY,
        bordercolor=COLOR_PRIMARY,
    )
    style.configure(
        "Treeview.Heading",
        background=COLOR_BG,
        foreground=COLOR_PRIMARY,
        font=FONT_BODY_BOLD,
    )
    style.map(
        "Treeview",
        background=[("selected", COLOR_PRIMARY)],
        foreground=[("selected", COLOR_BG)],
    )

    style.configure(
        "TProgressbar",
        background=COLOR_PRIMARY,
        foreground=COLOR_PRIMARY,
        troughcolor=COLOR_SURFACE,
        bordercolor=COLOR_SURFACE,
        lightcolor=COLOR_PRIMARY,
        darkcolor=COLOR_PRIMARY,
    )

    root_widget = root or style.master
    if isinstance(root_widget, (tk.Tk, tk.Toplevel)):
        try:
            root_widget.configure(bg=COLOR_BG)
        except Exception:
            pass

    if root_widget is not None:
        try:
            root_widget.option_add("*Font", FONT_BODY)
            root_widget.option_add("*Label.Font", FONT_BODY)
            root_widget.option_add("*Button.Font", FONT_BODY_BOLD)
            root_widget.option_add("*foreground", COLOR_TEXT)
        except Exception:
            pass


def paint_grid_background(target: Misc, spacing: int = 48) -> Optional[Canvas]:
    """Draw a cyan grid background behind ``target``."""

    try:
        canvas = Canvas(target, bg=COLOR_BG, highlightthickness=0, bd=0)
    except Exception:
        return None

    canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
    canvas.lower()

    def _draw(_event: object | None = None) -> None:
        try:
            width = max(1, target.winfo_width())
            height = max(1, target.winfo_height())
        except Exception:
            return
        canvas.delete("grid")
        for x in range(0, width, spacing):
            canvas.create_line(x, 0, x, height, fill=COLOR_GRID, width=1, tags="grid", dash=(2, 4))
        for y in range(0, height, spacing):
            canvas.create_line(0, y, width, y, fill=COLOR_GRID, width=1, tags="grid", dash=(2, 4))

    try:
        target.bind("<Configure>", _draw, add=True)
    except Exception:
        pass
    _draw()
    return canvas


def neon_border(
    widget: Misc,
    *,
    padding: int = 6,
    radius: int = 16,
    color: str = COLOR_PRIMARY,
) -> Optional[Canvas]:
    """Draw a rounded neon border behind ``widget`` using a canvas."""

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

    def _update(_event: object | None = None) -> None:
        try:
            x = widget.winfo_x()
            y = widget.winfo_y()
            w = widget.winfo_width()
            h = widget.winfo_height()
        except Exception:
            return
        if w <= 1 or h <= 1:
            widget.after(40, _update)
            return
        border_canvas.place(
            x=max(0, x - padding),
            y=max(0, y - padding),
            width=w + padding * 2,
            height=h + padding * 2,
        )
        border_canvas.lower(widget)
        border_canvas.delete("border")
        _rounded_rect(border_canvas, 1, 1, max(2, w + padding * 2 - 1), max(2, h + padding * 2 - 1), radius)

    try:
        widget.bind("<Configure>", _update, add=True)
        master.bind("<Configure>", _update, add=True)
    except Exception:
        pass
    widget.after(10, _update)
    return border_canvas

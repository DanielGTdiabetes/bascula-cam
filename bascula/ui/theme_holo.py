"""Holographic ttk theme helpers for the Báscula UI."""
from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import Canvas, Misc, ttk
from tkinter import font as tkfont
from typing import Iterable, Optional, Sequence

__all__ = [
    "apply_holo_theme",
    "get_style",
    "paint_grid_background",
    "neon_border",
    "draw_neon_separator",
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

PALETTE.update(
    {
        "neon_fuchsia": PALETTE["accent"],
        "neon_blue": "#6fe1ff",
    }
)


_STYLE: ttk.Style | None = None


def get_style(root: Optional[Misc] = None) -> ttk.Style:
    """Return a shared ``ttk.Style`` instance bound to ``root`` when possible."""

    global _STYLE

    if _STYLE is not None:
        master = getattr(_STYLE, "master", None)
        master_exists = True
        if master is not None:
            try:
                master_exists = bool(master.winfo_exists())
            except Exception:
                master_exists = False
        if not master_exists:
            _STYLE = None
        elif root is not None and master not in (None, root):
            # Recreate the style to avoid leaking references to previous roots
            # when tests or dialogs spawn independent Tk instances.
            _STYLE = None

    if _STYLE is None:
        _STYLE = ttk.Style(root)
    return _STYLE


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


def _mix_hex(color: str, other: str, mix: float) -> str:
    mix = max(0.0, min(1.0, mix))
    try:
        color_value = color.lstrip("#")
        other_value = other.lstrip("#")
        if len(color_value) != 6 or len(other_value) != 6:
            raise ValueError
        r1, g1, b1 = (int(color_value[i : i + 2], 16) for i in (0, 2, 4))
        r2, g2, b2 = (int(other_value[i : i + 2], 16) for i in (0, 2, 4))
        r = int(r1 * (1 - mix) + r2 * mix)
        g = int(g1 * (1 - mix) + g2 * mix)
        b = int(b1 * (1 - mix) + b2 * mix)
    except Exception:
        return color
    return f"#{r:02x}{g:02x}{b:02x}"


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

    style = get_style(root)
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

    style.layout("Ghost.Accent.TButton", style.layout("TButton"))
    style.configure(
        "Ghost.Accent.TButton",
        background=PALETTE["bg"],
        foreground=PALETTE["neon_fuchsia"],
        borderwidth=0,
        padding=8,
    )
    style.map(
        "Ghost.Accent.TButton",
        foreground=[("active", PALETTE["neon_fuchsia"])],
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


def draw_neon_separator(
    canvas: Canvas,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    *,
    color: str = "#00E5FF",
    tags: str = "holo-separator",
) -> None:
    """Render a holographic neon separator line between two coordinates."""

    try:
        start_x = int(x0)
        end_x = int(x1)
        start_y = int(y0)
        end_y = int(y1)
    except Exception:
        return

    if end_x == start_x and end_y == start_y:
        return

    if end_x < start_x:
        start_x, end_x = end_x, start_x
    if end_y < start_y:
        start_y, end_y = end_y, start_y

    if end_x - start_x <= 0:
        return

    glow_color = _mix_hex(color, COLOR_BG, 0.55)
    highlight = _mix_hex(color, "#ffffff", 0.3)

    # For horizontal separators keep the lines centred using the midpoint to
    # preserve the glow effect regardless of canvas height.
    if abs(end_y - start_y) <= 4:
        centre_y = start_y if start_y == end_y else int((start_y + end_y) / 2)
        base_y = centre_y
    else:
        base_y = start_y
        centre_y = int((start_y + end_y) / 2)

    canvas.delete(tags)
    canvas.create_line(start_x, base_y, end_x, base_y, width=6, fill=glow_color, capstyle=tk.ROUND, tags=tags)
    canvas.create_line(start_x, base_y, end_x, base_y, width=2, fill=color, capstyle=tk.ROUND, tags=tags)
    canvas.create_line(start_x, max(centre_y - 2, 0), end_x, max(centre_y - 2, 0), width=1, fill=highlight, capstyle=tk.ROUND, tags=tags)


def paint_grid_background(target: Misc, spacing: int = 48) -> Optional[Canvas]:
    """Draw a cyan grid background behind ``target``."""

    try:
        canvas = Canvas(target, bg=COLOR_BG, highlightthickness=0, bd=0)
    except Exception:
        return None

    canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
    try:
        tk.Misc.lower(canvas)
    except Exception:
        # Canvas.lower() would invoke tag_lower and crash; guard to avoid hard failures
        pass

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
    """Draw a rounded neon border around ``widget`` using an overlay canvas."""

    try:
        bg = widget.cget("background")
    except Exception:
        bg = COLOR_BG

    try:
        border_canvas = Canvas(widget, highlightthickness=0, bd=0, bg=bg)
    except Exception:
        return None

    border_canvas.place(relx=0, rely=0, relwidth=1, relheight=1)

    def _raise_content() -> None:
        parent = getattr(border_canvas, "master", None)
        if parent is None:
            return
        try:
            siblings = parent.winfo_children()
        except Exception:
            return
        for sibling in siblings:
            if sibling is border_canvas:
                continue
            try:
                sibling.lift()
            except Exception:
                continue

    try:
        widget.after_idle(_raise_content)
    except Exception:
        _raise_content()

    glow_color = _mix_hex(color, COLOR_BG, 0.45)
    highlight_color = _mix_hex(color, "#ffffff", 0.35)

    def _draw_round(
        canvas: Canvas,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        rad: int,
        *,
        outline: str,
        width: int,
        tags: tuple[str, ...],
    ) -> None:
        radius_px = max(0, min(int(rad), int((x1 - x0) / 2), int((y1 - y0) / 2)))
        if radius_px <= 0:
            canvas.create_rectangle(x0, y0, x1, y1, outline=outline, width=width, tags=tags)
            return
        arc_opts = {
            "style": tk.ARC,
            "outline": outline,
            "width": width,
            "tags": tags,
        }
        canvas.create_arc(x0, y0, x0 + 2 * radius_px, y0 + 2 * radius_px, start=90, extent=90, **arc_opts)
        canvas.create_arc(x1 - 2 * radius_px, y0, x1, y0 + 2 * radius_px, start=0, extent=90, **arc_opts)
        canvas.create_arc(x1 - 2 * radius_px, y1 - 2 * radius_px, x1, y1, start=270, extent=90, **arc_opts)
        canvas.create_arc(x0, y1 - 2 * radius_px, x0 + 2 * radius_px, y1, start=180, extent=90, **arc_opts)
        line_opts = {
            "fill": outline,
            "width": width,
            "tags": tags,
            "capstyle": tk.ROUND,
        }
        canvas.create_line(x0 + radius_px, y0, x1 - radius_px, y0, **line_opts)
        canvas.create_line(x1, y0 + radius_px, x1, y1 - radius_px, **line_opts)
        canvas.create_line(x0 + radius_px, y1, x1 - radius_px, y1, **line_opts)
        canvas.create_line(x0, y0 + radius_px, x0, y1 - radius_px, **line_opts)

    def _redraw(_event: object | None = None) -> None:
        try:
            widget.update_idletasks()
        except Exception:
            pass
        try:
            w = int(widget.winfo_width())
            h = int(widget.winfo_height())
        except Exception:
            return
        if w <= 2 or h <= 2:
            border_canvas.delete("neon")
            return
        border_canvas.configure(width=w, height=h)
        border_canvas.delete("neon")

        try:
            _raise_content()
        except Exception:
            pass

        inset = max(1, int(padding))
        x0 = inset + 1
        y0 = inset + 1
        x1 = w - inset - 1
        y1 = h - inset - 1
        if x1 <= x0 or y1 <= y0:
            return

        outer_radius = max(4, min(int(radius), int(min(x1 - x0, y1 - y0) / 2)))
        _draw_round(border_canvas, x0, y0, x1, y1, outer_radius, outline=glow_color, width=4, tags=("neon", "glow"))
        _draw_round(border_canvas, x0, y0, x1, y1, outer_radius, outline=color, width=2, tags=("neon", "stroke"))
        inner_radius = max(2, outer_radius - 2)
        _draw_round(
            border_canvas,
            x0 + 1,
            y0 + 1,
            x1 - 1,
            y1 - 1,
            inner_radius,
            outline=highlight_color,
            width=1,
            tags=("neon", "highlight"),
        )

    try:
        widget.bind("<Configure>", _redraw, add=True)
        border_canvas.bind("<Configure>", _redraw, add=True)
    except Exception:
        pass
    widget.after(20, _redraw)
    return border_canvas

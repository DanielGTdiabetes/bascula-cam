# bascula/config/theme.py
# Retro Green-on-Black Theme for Tkinter/ttk
# Drop-in theme that does NOT require external fonts.
# Usage (early in your app, right after creating Tk() root):
#   from bascula.config.theme import apply_theme
#   apply_theme(root)
#
# This module centralizes palette, fonts and ttk style names for the whole app.
# If your app already had a theme module, this file replaces it completely.

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# ------------------------------
# Palette & constants
# ------------------------------

# Primary "CRT green" and shades
CRT_BG         = "#000000"   # absolute black
CRT_FG         = "#00ff66"   # bright retro green
CRT_FG_DIM     = "#00cc55"   # dimmer green for secondary text
CRT_FG_FADE    = "#009944"   # further dim
CRT_OUTLINE    = "#00ff66"   # borders
CRT_ACCENT     = "#00ff99"   # accents/hover
CRT_WARN       = "#ffee33"   # warnings (amber) within retro style
CRT_ERROR      = "#ff3366"   # errors (magenta/red) within retro style
CRT_OK         = "#44ff88"   # ok/positive

# Optional scanline overlay color (disabled by default)
ENABLE_SCANLINES = False

# Font stack: prefer monospaced; fallback to system mono
FONT_FAMILY_MONO = ("DejaVu Sans Mono", "Liberation Mono", "Courier New", "Courier", "Monospace")

# Base font sizes (can be adjusted globally via set_scale)
FS_XS   = 9
FS_SM   = 11
FS_BASE = 12
FS_MD   = 13
FS_LG   = 16
FS_XL   = 20
FS_XXL  = 28
FS_NUM  = 42  # big numeric readouts

# UI metrics
PAD_X    = 8
PAD_Y    = 6
BORDER_W = 2
RADIUS   = 0  # ttk can't draw radius; keep for future custom widgets

# ------------------------------
# Public API
# ------------------------------

def apply_theme(root: tk.Tk | tk.Toplevel, *, scale: float = 1.0) -> None:
    """
    Apply the retro green-on-black theme to the given Tk root or Toplevel.
    Call this *right after* creating the Tk root, before constructing widgets.
    """
    # Global colors
    root.configure(bg=CRT_BG)
    _setup_fonts(scale)
    _setup_tk_defaults(root)
    _setup_style(root)

def set_scale(new_scale: float) -> None:
    """Optionally adjust base font sizes before building UI."""
    global FS_XS, FS_SM, FS_BASE, FS_MD, FS_LG, FS_XL, FS_XXL, FS_NUM
    FS_XS   = int(round(FS_XS   * new_scale))
    FS_SM   = int(round(FS_SM   * new_scale))
    FS_BASE = int(round(FS_BASE * new_scale))
    FS_MD   = int(round(FS_MD   * new_scale))
    FS_LG   = int(round(FS_LG   * new_scale))
    FS_XL   = int(round(FS_XL   * new_scale))
    FS_XXL  = int(round(FS_XXL  * new_scale))
    FS_NUM  = int(round(FS_NUM  * new_scale))

# ------------------------------
# Internal helpers
# ------------------------------

def _preferred_mono() -> str:
    # tk doesn't support font fallback lists directly; pick the first available
    test = tk.font.families() if hasattr(tk, 'font') else []
    for fam in FONT_FAMILY_MONO:
        try:
            if fam in test:
                return fam
        except Exception:
            pass
    return "TkFixedFont"

def _setup_fonts(scale: float) -> None:
    import tkinter.font as tkfont
    if scale != 1.0:
        tkfont.nametofont("TkDefaultFont").configure(size=int(FS_BASE * scale))
        tkfont.nametofont("TkTextFont").configure(size=int(FS_BASE * scale))
        tkfont.nametofont("TkMenuFont").configure(size=int(FS_BASE * scale))
        tkfont.nametofont("TkFixedFont").configure(size=int(FS_BASE * scale))

    mono = _preferred_mono()
    # Create named fonts for reuse
    tkfont.Font(name="Retro/Base", family=mono, size=FS_BASE)
    tkfont.Font(name="Retro/Small", family=mono, size=FS_SM)
    tkfont.Font(name="Retro/Medium", family=mono, size=FS_MD, weight="bold")
    tkfont.Font(name="Retro/Large", family=mono, size=FS_LG, weight="bold")
    tkfont.Font(name="Retro/XL", family=mono, size=FS_XL, weight="bold")
    tkfont.Font(name="Retro/XXL", family=mono, size=FS_XXL, weight="bold")
    tkfont.Font(name="Retro/Number", family=mono, size=FS_NUM, weight="bold")

def _setup_tk_defaults(root: tk.Misc) -> None:
    # Default widget colors for classic Tk widgets (Labels, Frames, Canvas, etc.)
    root.option_add("*background", CRT_BG)
    root.option_add("*foreground", CRT_FG)
    root.option_add("*selectBackground", CRT_FG_FADE)
    root.option_add("*selectForeground", CRT_BG)
    root.option_add("*insertBackground", CRT_FG)
    root.option_add("*highlightThickness", 0)
    root.option_add("*font", "Retro/Base")

def _setup_style(root: tk.Misc) -> None:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    # General colors for ttk
    style.configure(".", background=CRT_BG, foreground=CRT_FG, fieldbackground=CRT_BG, bordercolor=CRT_OUTLINE, lightcolor=CRT_OUTLINE, darkcolor=CRT_OUTLINE, troughcolor="#001a0c")
    style.map(".", foreground=[("disabled", CRT_FG_FADE)], background=[("disabled", CRT_BG)])

    # Buttons (Retro/Primary)
    style.configure("Retro.TButton",
                    font="Retro/Medium",
                    padding=(PAD_X, PAD_Y),
                    relief="flat",
                    borderwidth=BORDER_W,
                    background=CRT_BG,
                    foreground=CRT_FG,
                    focuscolor=CRT_OUTLINE,
                    anchor="center")
    style.map("Retro.TButton",
              foreground=[("pressed", CRT_BG), ("active", CRT_BG)],
              background=[("pressed", CRT_ACCENT), ("active", CRT_ACCENT)],
              bordercolor=[("!disabled", CRT_OUTLINE)])

    # Secondary (small) button
    style.configure("Retro.S.TButton",
                    font="Retro/Small",
                    padding=(PAD_X-2, PAD_Y-2),
                    relief="flat",
                    borderwidth=BORDER_W,
                    background=CRT_BG,
                    foreground=CRT_FG)
    style.map("Retro.S.TButton",
              foreground=[("pressed", CRT_BG), ("active", CRT_BG)],
              background=[("pressed", CRT_ACCENT), ("active", CRT_ACCENT)])

    # Labels
    style.configure("Retro.TLabel", font="Retro/Base", background=CRT_BG, foreground=CRT_FG)
    style.configure("Retro.M.TLabel", font="Retro/Medium", background=CRT_BG, foreground=CRT_FG)
    style.configure("Retro.L.TLabel", font="Retro/Large", background=CRT_BG, foreground=CRT_FG)
    style.configure("Retro.Num.TLabel", font="Retro/Number", background=CRT_BG, foreground=CRT_FG)

    # Frames
    style.configure("Retro.TFrame", background=CRT_BG, borderwidth=0)
    style.configure("Retro.Card.TFrame", background=CRT_BG, relief="flat", borderwidth=BORDER_W)

    # Entry
    style.configure("Retro.TEntry",
                    padding=(PAD_X, PAD_Y),
                    font="Retro/Base",
                    fieldbackground=CRT_BG,
                    foreground=CRT_FG,
                    bordercolor=CRT_OUTLINE,
                    borderwidth=BORDER_W,
                    relief="flat")
    style.map("Retro.TEntry",
              foreground=[("disabled", CRT_FG_DIM)],
              fieldbackground=[("readonly", "#001a0c"), ("focus", CRT_BG)],
              bordercolor=[("focus", CRT_ACCENT)])

    # Checkbutton / Radiobutton
    style.configure("Retro.TCheckbutton", background=CRT_BG, foreground=CRT_FG, font="Retro/Base")
    style.configure("Retro.TRadiobutton", background=CRT_BG, foreground=CRT_FG, font="Retro/Base")

    # Notebook (tabs)
    style.configure("Retro.TNotebook", background=CRT_BG, borderwidth=0)
    style.configure("Retro.TNotebook.Tab",
                    background=CRT_BG,
                    foreground=CRT_FG_DIM,
                    padding=(PAD_X, PAD_Y),
                    font="Retro/Small",
                    borderwidth=BORDER_W)
    style.map("Retro.TNotebook.Tab",
              background=[("selected", "#001a0c"), ("active", "#001a0c")],
              foreground=[("selected", CRT_FG), ("active", CRT_ACCENT)],
              bordercolor=[("selected", CRT_OUTLINE), ("active", CRT_ACCENT)])

    # Scrollbar
    style.configure("Retro.Vertical.TScrollbar", background=CRT_BG, troughcolor="#001a0c", bordercolor=CRT_OUTLINE, arrowcolor=CRT_FG)
    style.configure("Retro.Horizontal.TScrollbar", background=CRT_BG, troughcolor="#001a0c", bordercolor=CRT_OUTLINE, arrowcolor=CRT_FG)

    # Progressbar
    style.configure("Retro.Horizontal.TProgressbar", troughcolor="#001a0c", background=CRT_ACCENT, bordercolor=CRT_OUTLINE)

    # Treeview
    style.configure("Retro.Treeview",
                    background=CRT_BG,
                    fieldbackground=CRT_BG,
                    foreground=CRT_FG,
                    bordercolor=CRT_OUTLINE,
                    rowheight=24,
                    font="Retro/Small")
    style.configure("Retro.Treeview.Heading",
                    background="#001a0c",
                    foreground=CRT_FG,
                    font="Retro/Small",
                    bordercolor=CRT_OUTLINE)
    style.map("Retro.Treeview.Heading",
              background=[("active", CRT_ACCENT)])

    # Message colors (use these tags/classes in your UI as needed)
    style.configure("Retro/Ok.TLabel", foreground=CRT_OK)
    style.configure("Retro/Warn.TLabel", foreground=CRT_WARN)
    style.configure("Retro/Error.TLabel", foreground=CRT_ERROR)

    # Default style fallbacks (so existing widgets pick up retro look without code changes)
    style.configure("TLabel", background=CRT_BG, foreground=CRT_FG, font="Retro/Base")
    style.configure("TFrame", background=CRT_BG)
    style.configure("TEntry", fieldbackground=CRT_BG, foreground=CRT_FG, bordercolor=CRT_OUTLINE, borderwidth=BORDER_W, relief="flat", padding=(PAD_X, PAD_Y))
    style.configure("TButton", background=CRT_BG, foreground=CRT_FG, borderwidth=BORDER_W, relief="flat", padding=(PAD_X, PAD_Y), font="Retro/Medium")

    # Optional: fake scanlines by overlaying a canvas. Off by default.
    if ENABLE_SCANLINES:
        _install_scanlines(root)

def _install_scanlines(root: tk.Misc) -> None:
    # Adds a transparent-like scanline overlay. It sits on top of root & ignores events.
    # Warning: this is purely cosmetic and may reduce performance on Pi Zero.
    overlay = tk.Canvas(root, highlightthickness=0, bd=0, bg=CRT_BG)
    overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
    h = 2
    def draw():
        overlay.delete("all")
        w = overlay.winfo_width()
        height = overlay.winfo_height()
        for y in range(0, height, h*2):
            overlay.create_rectangle(0, y, w, y+h, outline="", fill="#000000")
        overlay.after(1000, draw)
    overlay.bind("<Configure>", lambda e: draw())
    overlay.lower()  # stay below to not intercept events


"""Reusable Tk widgets and theme helpers for the Holographic UI."""
from __future__ import annotations

from typing import Callable, Optional

import tkinter as tk
from tkinter import ttk

# ---------------------------------------------------------------------------
# Palette (defaults are overridden by runtime theme manager when available)
# ---------------------------------------------------------------------------
COL_BG = "#0A0A0A"
COL_GRID = "#083A40"
COL_TEXT = "#FFFFFF"
COL_PLACEHOLDER = "#FFFFFF80"
COL_PRIMARY = "#00E5FF"
COL_ACCENT = "#FF00DC"
COL_ACCENT_LIGHT = "#FF55F0"
COL_CARD = "#111827"
COL_CARD_ALT = "#141B2C"
COL_CARD_HOVER = "#1B2336"
COL_MUTED = "#9AA6C5"
COL_SUCCESS = "#00FFC8"
COL_WARN = "#FFE27A"
COL_DANGER = "#FF4F7D"
COL_BORDER = "#00A7C6"
COL_TRACK_OFF = "#333333"
COL_THUMB_OFF = "#DDDDDD"

# Simulated "glow" borders using Tk highlight options
BORDER_PRIMARY_THIN = {"highlightbackground": COL_PRIMARY, "highlightcolor": COL_PRIMARY, "highlightthickness": 1}
BORDER_PRIMARY = {"highlightbackground": COL_PRIMARY, "highlightcolor": COL_PRIMARY, "highlightthickness": 2}
BORDER_ACCENT = {"highlightbackground": COL_ACCENT, "highlightcolor": COL_ACCENT, "highlightthickness": 2}


# Compatibility palette used by legacy screens
PALETTE = {
    "bg": COL_BG,
    "panel": COL_CARD,
    "accent": COL_PRIMARY,
    "accent_hover": COL_ACCENT,
    "text": COL_TEXT,
    "muted": COL_MUTED,
}


# ---------------------------------------------------------------------------
# Typography
# ---------------------------------------------------------------------------
FONT_FAMILY_BODY = ("Oxanium", 12)
FONT_FAMILY_TITLE = ("Oxanium", 20, "bold")
FONT_FAMILY_NUMBER = ("Share Tech Mono", 32)

FS_TITLE = 20
FS_CARD_TITLE = 16
FS_TEXT = 13
FS_BTN_SMALL = 12

FONT_LG = (FONT_FAMILY_BODY[0], FS_TITLE, "bold")
FONT_MD = (FONT_FAMILY_BODY[0], FS_CARD_TITLE, "bold")
FONT_SM = (FONT_FAMILY_BODY[0], FS_TEXT)


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------
def auto_apply_scaling(widget: tk.Misc) -> None:
    """Approximate DPI scaling for the current display (best effort)."""

    try:
        pixels_per_inch = widget.winfo_fpixels("1i")
        scaling = max(1.0, float(pixels_per_inch) / 72.0)
        widget.tk.call("tk", "scaling", scaling)
    except Exception:
        pass


def _configure_button_hover(widget: tk.Button, base_bg: str, hover_bg: str, *, hover_fg: Optional[str] = None) -> None:
    def _on_enter(_event: tk.Event) -> None:
        widget.configure(bg=hover_bg)
        if hover_fg:
            widget.configure(fg=hover_fg)

    def _on_leave(_event: tk.Event) -> None:
        widget.configure(bg=base_bg)
        if hover_fg:
            widget.configure(fg=COL_TEXT)

    widget.bind("<Enter>", _on_enter, add=True)
    widget.bind("<Leave>", _on_leave, add=True)


def apply_holo_tabs_style(root: tk.Misc) -> None:
    """Apply notebook/tab styling suitable for the Holographic theme."""

    style = ttk.Style(root)
    try:
        current = style.theme_use()
        style.theme_use(current)
    except Exception:
        pass

    style.configure(
        "Holo.TNotebook",
        background=COL_BG,
        borderwidth=0,
        tabmargins=(8, 4, 8, 0),
    )
    style.configure(
        "Holo.TNotebook.Tab",
        padding=(20, 10),
        background=COL_BG,
        foreground=COL_TEXT,
        font=FONT_FAMILY_BODY,
        borderwidth=0,
    )
    style.map(
        "Holo.TNotebook.Tab",
        foreground=[("selected", COL_ACCENT)],
        background=[("selected", COL_BG)],
    )


def use_holo_notebook(notebook: ttk.Notebook) -> None:
    notebook.configure(style="Holo.TNotebook")


def style_holo_checkbuttons(root: tk.Misc) -> None:
    """Configure ttk/tk checkbuttons to resemble neon toggles."""

    style = ttk.Style(root)
    style.configure(
        "Holo.TCheckbutton",
        background=COL_CARD,
        foreground=COL_TEXT,
        focuscolor=COL_ACCENT,
        indicatordiameter=18,
        padding=6,
        font=FONT_FAMILY_BODY,
    )
    style.map(
        "Holo.TCheckbutton",
        foreground=[("selected", COL_ACCENT)],
        background=[("active", COL_CARD_HOVER)],
    )
    style.configure(
        "TCombobox",
        fieldbackground=COL_CARD_HOVER,
        background=COL_CARD_HOVER,
        foreground=COL_TEXT,
        arrowcolor=COL_PRIMARY,
    )
    style.map(
        "TCombobox",
        fieldbackground=[("readonly", COL_CARD_HOVER)],
        foreground=[("disabled", COL_MUTED)],
    )


def apply_holo_theme_to_tree(root: tk.Misc) -> None:
    """Recursively restyle legacy Tk widgets inside a container."""

    queue: list[tk.Misc] = [root]
    while queue:
        widget = queue.pop()
        try:
            children = list(widget.winfo_children())
        except Exception:
            children = []
        queue.extend(children)

        try:
            if isinstance(widget, (tk.Tk, tk.Toplevel)):
                widget.configure(bg=COL_BG)
            elif isinstance(widget, tk.Frame):
                widget.configure(bg=COL_CARD)
            elif isinstance(widget, tk.Label):
                widget.configure(bg=COL_CARD, fg=COL_TEXT, font=FONT_SM)
            elif isinstance(widget, tk.Entry):
                widget.configure(
                    bg=COL_CARD_HOVER,
                    fg=COL_TEXT,
                    insertbackground=COL_ACCENT,
                    relief="flat",
                    highlightthickness=2,
                    highlightbackground=COL_PRIMARY,
                    highlightcolor=COL_ACCENT,
                )
                widget.bind(
                    "<FocusIn>",
                    lambda _e, w=widget: w.configure(highlightbackground=COL_ACCENT, highlightcolor=COL_ACCENT, fg=COL_ACCENT),
                    add=True,
                )
                widget.bind(
                    "<FocusOut>",
                    lambda _e, w=widget: w.configure(highlightbackground=COL_PRIMARY, highlightcolor=COL_ACCENT, fg=COL_TEXT),
                    add=True,
                )
            elif isinstance(widget, tk.Checkbutton):
                widget.configure(
                    bg=COL_CARD,
                    fg=COL_TEXT,
                    activebackground=COL_CARD,
                    activeforeground=COL_ACCENT,
                    selectcolor=COL_CARD,
                    highlightthickness=1,
                    highlightbackground=COL_PRIMARY,
                )
            elif isinstance(widget, tk.Button):
                widget.configure(
                    bg=COL_BG,
                    fg=COL_TEXT,
                    activebackground=COL_BG,
                    activeforeground=COL_ACCENT,
                    relief="flat",
                    cursor="hand2",
                    highlightthickness=1,
                    highlightbackground=COL_PRIMARY,
                )
                widget.bind(
                    "<Enter>",
                    lambda _e, w=widget: w.configure(fg=COL_ACCENT, highlightbackground=COL_ACCENT),
                    add=True,
                )
                widget.bind(
                    "<Leave>",
                    lambda _e, w=widget: w.configure(fg=COL_TEXT, highlightbackground=COL_PRIMARY),
                    add=True,
                )
            elif isinstance(widget, ttk.Checkbutton):
                widget.configure(style="Holo.TCheckbutton")
            elif isinstance(widget, ttk.Combobox):
                widget.configure(style="TCombobox")
                widget.configure(foreground=COL_TEXT)
            elif isinstance(widget, tk.Text):
                widget.configure(bg=COL_CARD_HOVER, fg=COL_TEXT, insertbackground=COL_ACCENT, relief="flat")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Reusable widget primitives
# ---------------------------------------------------------------------------
class Card(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        *,
        min_width: Optional[int] = None,
        min_height: Optional[int] = None,
        padding: int | tuple[int, int] = 16,
        **kwargs,
    ) -> None:
        bg = kwargs.pop("bg", COL_CARD)
        highlight = kwargs.pop("highlightthickness", BORDER_PRIMARY.get("highlightthickness", 2))
        super().__init__(
            master,
            bg=bg,
            bd=0,
            highlightbackground=COL_PRIMARY,
            highlightcolor=COL_PRIMARY,
            highlightthickness=highlight,
            **kwargs,
        )

        if min_width:
            self.configure(width=min_width)
        if min_height:
            self.configure(height=min_height)

        if isinstance(padding, tuple):
            pad_x, pad_y = padding
        else:
            pad_x = pad_y = int(padding)
        self._padding = (pad_x, pad_y)
        try:
            self.configure(padx=pad_x, pady=pad_y)
        except Exception:
            pass
        self._apply_padding()

    def _apply_padding(self) -> None:
        pad_x, pad_y = getattr(self, "_padding", (0, 0))
        for child in self.winfo_children():
            if isinstance(child, tk.Frame) and getattr(child, "_holo_card_child", False):
                child.pack_configure(padx=pad_x, pady=pad_y)

    def content(self) -> "Card":
        return self

    def add_glass_layer(self) -> tk.Frame:
        inner = tk.Frame(self, bg=COL_CARD_ALT)
        inner._holo_card_child = True  # type: ignore[attr-defined]
        inner.pack(expand=True, fill="both")
        self._apply_padding()
        return inner


class PrimaryButton(tk.Button):
    def __init__(self, master: tk.Misc, text: str, command: Callable[..., None], **kwargs):
        bg = kwargs.pop("bg", COL_ACCENT)
        fg = kwargs.pop("fg", COL_TEXT)
        font = kwargs.pop("font", FONT_FAMILY_TITLE)
        super().__init__(
            master,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            activebackground=COL_ACCENT_LIGHT,
            activeforeground=COL_TEXT,
            relief="flat",
            bd=0,
            padx=22,
            pady=16,
            font=font,
            cursor="hand2",
            highlightthickness=2,
            highlightbackground=COL_BORDER,
            highlightcolor=COL_BORDER,
            **kwargs,
        )
        _configure_button_hover(self, bg, COL_ACCENT_LIGHT)


class ToolbarButton(tk.Button):
    def __init__(self, master: tk.Misc, text: str, command: Callable[..., None], **kwargs):
        font = kwargs.pop("font", FONT_FAMILY_BODY)
        super().__init__(
            master,
            text=text,
            command=command,
            bg=COL_BG,
            fg=COL_PRIMARY,
            activebackground=COL_BG,
            activeforeground=COL_ACCENT,
            relief="flat",
            bd=0,
            padx=14,
            pady=10,
            font=font,
            cursor="hand2",
            highlightthickness=1,
            highlightbackground=COL_PRIMARY,
            highlightcolor=COL_PRIMARY,
            **kwargs,
        )
        _configure_button_hover(self, COL_BG, COL_CARD_HOVER, hover_fg=COL_ACCENT)


class BigButton(tk.Button):
    def __init__(
        self,
        master: tk.Misc,
        *,
        text: str,
        command: Callable[..., None],
        bg: str | None = None,
        small: bool = False,
        micro: bool = False,
        **kwargs,
    ) -> None:
        size = FS_TEXT if small else FS_TITLE
        if micro:
            size = max(10, FS_BTN_SMALL)
        font = kwargs.pop("font", (FONT_FAMILY_BODY[0], size, "bold"))
        base_bg = bg or COL_ACCENT
        super().__init__(
            master,
            text=text,
            command=command,
            bg=base_bg,
            fg=COL_TEXT,
            activebackground=COL_ACCENT_LIGHT,
            activeforeground=COL_TEXT,
            relief="flat",
            bd=0,
            padx=18 if not micro else 10,
            pady=12 if not micro else 6,
            font=font,
            cursor="hand2",
            highlightthickness=2,
            highlightbackground=COL_BORDER,
            highlightcolor=COL_BORDER,
            **kwargs,
        )
        _configure_button_hover(self, base_bg, COL_ACCENT_LIGHT)


class GhostButton(tk.Button):
    def __init__(
        self,
        master: tk.Misc,
        *,
        text: str,
        command: Callable[..., None],
        micro: bool = False,
        **kwargs,
    ) -> None:
        pad_x = 16 if not micro else 10
        pad_y = 10 if not micro else 6
        font = kwargs.pop("font", (FONT_FAMILY_BODY[0], FS_BTN_SMALL if micro else FS_TEXT, "bold"))
        super().__init__(
            master,
            text=text,
            command=command,
            bg=COL_BG,
            fg=COL_PRIMARY,
            activebackground=COL_BG,
            activeforeground=COL_ACCENT,
            relief="flat",
            bd=0,
            padx=pad_x,
            pady=pad_y,
            font=font,
            cursor="hand2",
            highlightthickness=1,
            highlightbackground=COL_PRIMARY,
            highlightcolor=COL_PRIMARY,
            **kwargs,
        )
        _configure_button_hover(self, COL_BG, COL_CARD_HOVER, hover_fg=COL_ACCENT)


class WeightDisplay(tk.Label):
    def __init__(self, master: tk.Misc, **kwargs):
        font = kwargs.pop("font", (FONT_FAMILY_NUMBER[0], 110, "bold"))
        super().__init__(
            master,
            text="--",
            font=font,
            fg=COL_ACCENT,
            bg=kwargs.pop("bg", COL_CARD),
            anchor="center",
            **kwargs,
        )

    def update_value(self, value: float, unit: str) -> None:
        self.configure(text=f"{value:.0f} {unit}")


class WeightLabel(tk.Label):
    def __init__(self, master: tk.Misc, **kwargs):
        super().__init__(
            master,
            text="0 g",
            font=(FONT_FAMILY_NUMBER[0], 72, "bold"),
            fg=COL_ACCENT,
            bg=kwargs.pop("bg", COL_CARD),
            **kwargs,
        )


class TotalsTable(ttk.Treeview):
    def __init__(self, master: tk.Misc) -> None:
        columns = ("name", "weight", "carbs", "protein", "fat", "gi")
        super().__init__(
            master,
            columns=columns,
            show="headings",
            height=6,
        )
        headings = {
            "name": "Alimento",
            "weight": "Peso (g)",
            "carbs": "HC (g)",
            "protein": "Prot (g)",
            "fat": "Grasa (g)",
            "gi": "IG",
        }
        for cid, label in headings.items():
            self.heading(cid, text=label)
            self.column(cid, width=120, anchor="center")
        self.column("name", width=200, anchor="w")

        style = ttk.Style(master)
        style.configure(
            "Holo.Treeview",
            background=COL_CARD_HOVER,
            foreground=COL_TEXT,
            fieldbackground=COL_CARD_HOVER,
            bordercolor=COL_PRIMARY,
            highlightthickness=0,
            rowheight=28,
        )
        style.map("Holo.Treeview", background=[("selected", COL_ACCENT)], foreground=[("selected", COL_BG)])
        self.configure(style="Holo.Treeview")


class Toast:
    """Minimal transient notification label."""

    def __init__(self, parent: tk.Misc) -> None:
        self.parent = parent
        self._label = tk.Label(
            parent,
            text="",
            bg=COL_ACCENT,
            fg=COL_BG,
            font=FONT_SM,
            bd=0,
            relief="flat",
            padx=16,
            pady=8,
        )
        self._after_id: Optional[str] = None

    def show(self, text: str, duration_ms: int = 1200, bg: Optional[str] = None) -> None:
        self._label.configure(text=str(text), bg=bg or COL_ACCENT, fg=COL_BG)
        self._label.place(relx=0.5, rely=0.02, anchor="n")

        if self._after_id:
            try:
                self.parent.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = self.parent.after(duration_ms, self.hide)

    def hide(self) -> None:
        try:
            self._label.place_forget()
        except Exception:
            pass
        self._after_id = None


class KeypadPopup(tk.Toplevel):
    """Simple keypad dialog used for quick numeric entry."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        title: str = "",
        initial: str = "",
        on_accept: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.transient(parent)
        self.title(title or "Keypad")
        self.configure(bg=COL_BG)
        self.resizable(False, False)

        self._value = tk.StringVar(value=str(initial))
        self._entry = tk.Entry(
            self,
            textvariable=self._value,
            bg=COL_CARD_HOVER,
            fg=COL_TEXT,
            insertbackground=COL_ACCENT,
            relief="flat",
        )
        self._entry.pack(fill="x", padx=16, pady=(16, 12))
        self._entry.focus_set()

        grid = tk.Frame(self, bg=COL_BG)
        grid.pack(padx=16, pady=(0, 12))

        buttons = [
            "7",
            "8",
            "9",
            "4",
            "5",
            "6",
            "1",
            "2",
            "3",
            "0",
            ".",
            "←",
        ]

        def _press(value: str) -> None:
            if value == "←":
                current = self._value.get()
                self._value.set(current[:-1])
            else:
                self._value.set(self._value.get() + value)

        for idx, val in enumerate(buttons):
            btn = tk.Button(
                grid,
                text=val,
                command=lambda v=val: _press(v),
                bg=COL_CARD,
                fg=COL_TEXT,
                activebackground=COL_CARD_HOVER,
                activeforeground=COL_ACCENT,
                relief="flat",
                width=4,
                cursor="hand2",
            )
            btn.grid(row=idx // 3, column=idx % 3, padx=6, pady=6, sticky="nsew")
            grid.grid_columnconfigure(idx % 3, weight=1)

        btns = tk.Frame(self, bg=COL_BG)
        btns.pack(fill="x", padx=16, pady=(0, 16))

        def _accept() -> None:
            if on_accept:
                try:
                    on_accept(self._value.get())
                except Exception:
                    pass
            self.destroy()

        def _cancel() -> None:
            self.destroy()

        BigButton(btns, text="Cancelar", command=_cancel, bg=COL_TRACK_OFF, small=True).pack(side="left", expand=True, fill="x", padx=(0, 8))
        BigButton(btns, text="Aceptar", command=_accept, bg=COL_ACCENT, small=True).pack(side="left", expand=True, fill="x")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
__all__ = [
    "PALETTE",
    "COL_BG",
    "COL_GRID",
    "COL_TEXT",
    "COL_PLACEHOLDER",
    "COL_PRIMARY",
    "COL_ACCENT",
    "COL_ACCENT_LIGHT",
    "COL_CARD",
    "COL_CARD_ALT",
    "COL_CARD_HOVER",
    "COL_MUTED",
    "COL_SUCCESS",
    "COL_WARN",
    "COL_DANGER",
    "COL_BORDER",
    "COL_TRACK_OFF",
    "COL_THUMB_OFF",
    "BORDER_PRIMARY_THIN",
    "BORDER_PRIMARY",
    "BORDER_ACCENT",
    "FONT_FAMILY_BODY",
    "FONT_FAMILY_TITLE",
    "FONT_FAMILY_NUMBER",
    "FS_TITLE",
    "FS_CARD_TITLE",
    "FS_TEXT",
    "FS_BTN_SMALL",
    "PrimaryButton",
    "ToolbarButton",
    "BigButton",
    "GhostButton",
    "Card",
    "WeightDisplay",
    "WeightLabel",
    "TotalsTable",
    "Toast",
    "KeypadPopup",
    "auto_apply_scaling",
    "apply_holo_tabs_style",
    "use_holo_notebook",
    "style_holo_checkbuttons",
    "apply_holo_theme_to_tree",
]

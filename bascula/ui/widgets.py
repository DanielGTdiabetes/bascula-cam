
"""Reusable Tk widgets and theme helpers for the Holographic UI."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable, Optional

import tkinter as tk
from tkinter import ttk

from . import theme_holo
from .fonts import font_tuple, get_mono_font_family, get_ui_font_family


LOGGER = logging.getLogger(__name__)

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
FONT_FAMILY_BODY = (get_ui_font_family(), 12)
FONT_FAMILY_TITLE = (get_ui_font_family(), 20, "bold")
FONT_FAMILY_NUMBER = (get_mono_font_family(), 32)

FS_TITLE = 20
FS_CARD_TITLE = 16
FS_TEXT = 13
FS_BTN_SMALL = 12

FONT_LG = font_tuple(FS_TITLE, "bold")
FONT_MD = font_tuple(FS_CARD_TITLE, "bold")
FONT_SM = font_tuple(FS_TEXT)


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


class NeoGhostButton(tk.Canvas):
    """Rounded neon-outline button rendered on a canvas."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        width: int = 160,
        height: int = 80,
        radius: int = 18,
        outline_color: str | None = None,
        outline_width: int = 2,
        text: str | None = None,
        icon: tk.PhotoImage | None = None,
        icon_path: str | Path | None = None,
        command: Callable[[], None] | None = None,
        tooltip: str | None = None,
        show_text: bool = False,
        text_color: str | None = None,
        font: Any | None = None,
        **kwargs: Any,
    ) -> None:
        bg_default = theme_holo.PALETTE.get("bg", theme_holo.COLOR_BG)
        if "background" not in kwargs and "bg" not in kwargs:
            kwargs["bg"] = bg_default

        super().__init__(parent, highlightthickness=0, bd=0, **kwargs)

        self._bg_color = self.cget("bg")
        self._width_req = int(width)
        self._height_req = int(height)
        self._radius = max(4, int(radius))
        self._base_outline_width = max(1, int(outline_width))
        self._outline_color = outline_color or theme_holo.PALETTE.get("neon_fuchsia", theme_holo.COLOR_ACCENT)
        self._text_color = text_color or theme_holo.PALETTE.get("text", theme_holo.COLOR_TEXT)
        self._font = font or theme_holo.FONT_UI_BOLD
        self._accessible_text = text or ""
        self._tooltip_text = tooltip or self._accessible_text
        self._command = command
        self._show_text = bool(show_text)

        self._hover = False
        self._pressed = False
        self._focused = False

        self._tooltip_after: str | None = None
        self._tooltip_window: tk.Toplevel | None = None

        self._icon_source: Path | None = None
        self._icon_image: tk.PhotoImage | None = None
        self._image_name: str = ""

        if icon is not None:
            self._set_icon_image(icon)
        elif icon_path is not None:
            self._set_icon(icon_path)
        if self._icon_image is None:
            self._show_text = True if self._accessible_text else self._show_text

        self.configure(width=self._width_req, height=self._height_req, cursor="hand2", takefocus=1)

        self.bind("<Enter>", self._on_enter, add=True)
        self.bind("<Leave>", self._on_leave, add=True)
        self.bind("<ButtonPress-1>", self._on_press, add=True)
        self.bind("<ButtonRelease-1>", self._on_release, add=True)
        self.bind("<KeyRelease-space>", self._on_key_activate, add=True)
        self.bind("<KeyRelease-Return>", self._on_key_activate, add=True)
        self.bind("<FocusIn>", self._on_focus_in, add=True)
        self.bind("<FocusOut>", self._on_focus_out, add=True)
        self.bind("<Configure>", self._on_configure, add=True)

        self._render()

    def configure(self, cnf: Any | None = None, **kwargs: Any) -> None:  # type: ignore[override]
        if cnf:
            if isinstance(cnf, dict):
                kwargs.update(cnf)

        command = kwargs.pop("command", None)
        text = kwargs.pop("text", None)
        tooltip = kwargs.pop("tooltip", None)
        icon_path = kwargs.pop("icon_path", None)
        icon_image = kwargs.pop("icon", None)
        text_color = kwargs.pop("text_color", None)
        font = kwargs.pop("font", None)
        show_text = kwargs.pop("show_text", None)

        if command is not None:
            self._command = command  # type: ignore[assignment]
        if text is not None:
            self._accessible_text = str(text)
            if self._show_text or self._icon_image is None:
                self._show_text = True
        if tooltip is not None:
            self._tooltip_text = str(tooltip)
        if icon_image is not None:
            self._set_icon_image(icon_image)
        elif icon_path is not None:
            self._set_icon(icon_path)
        if text_color is not None:
            self._text_color = str(text_color)
        if font is not None:
            self._font = font
        if show_text is not None:
            self._show_text = bool(show_text) or (self._icon_image is None and bool(self._accessible_text))

        if kwargs:
            super().configure(**kwargs)
        self._render()

    config = configure

    def cget(self, key: str) -> Any:  # type: ignore[override]
        key_lower = key.lower()
        if key_lower in {"text", "label"}:
            return self._accessible_text
        if key_lower in {"fg", "foreground"}:
            return self._text_color
        if key_lower == "command":
            return self._command
        if key_lower == "image":
            return self._image_name
        if key_lower == "icon_path":
            return str(self._icon_source) if self._icon_source else ""
        return super().cget(key)

    def invoke(self) -> None:
        self._invoke()

    def destroy(self) -> None:
        self._cancel_tooltip()
        super().destroy()

    # ------------------------------------------------------------------
    def _set_icon(self, icon_path: str | Path) -> None:
        path = Path(icon_path)
        self._icon_source = path if path.exists() else None
        image: tk.PhotoImage | None = None
        if self._icon_source is not None:
            try:
                image = tk.PhotoImage(file=str(self._icon_source))
            except Exception:
                image = None
        self._set_icon_image(image, source=self._icon_source)
        if self._icon_source is None and image is None and self._accessible_text:
            self._show_text = True

    def _set_icon_image(self, image: tk.PhotoImage | None, *, source: Path | None = None) -> None:
        self._icon_source = source
        self._icon_image = image
        self._image_name = str(image) if image is not None else ""
        if self._icon_image is None and self._accessible_text:
            self._show_text = True

    def _render(self) -> None:
        self.delete("outline")
        self.delete("focus")
        self.delete("content")

        width = max(self._width_req, int(self.winfo_width() or self._width_req))
        height = max(self._height_req, int(self.winfo_height() or self._height_req))

        outline_width, radius = self._state_outline()
        pad = outline_width / 2 + 1
        x0 = pad
        y0 = pad
        x1 = width - pad
        y1 = height - pad

        if x1 <= x0 or y1 <= y0:
            return

        self._create_round_outline(x0, y0, x1, y1, radius, outline=self._outline_color, width=outline_width, tags="outline")

        if self._focused:
            self._create_round_outline(
                x0 - 3,
                y0 - 3,
                x1 + 3,
                y1 + 3,
                radius + 3,
                outline=theme_holo.PALETTE.get("primary", theme_holo.COLOR_PRIMARY),
                width=1,
                dash=(3, 2),
                tags="focus",
            )

        if self._icon_image is not None and not self._show_text:
            self.create_image(width // 2, height // 2, image=self._icon_image, tags="content")
        elif self._accessible_text:
            self.create_text(
                width // 2,
                height // 2,
                text=self._accessible_text,
                fill=self._text_color,
                font=self._font,
                tags="content",
            )

    def _state_outline(self) -> tuple[int, int]:
        outline_width = self._base_outline_width
        radius = self._radius
        if self._hover:
            outline_width += 1
        if self._pressed:
            outline_width += 1
            radius = max(4, radius - 1)
        return outline_width, radius

    def _create_round_outline(
        self,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        radius: int,
        **kwargs: Any,
    ) -> None:
        common = kwargs.copy()
        tags = common.pop("tags", ())
        if isinstance(tags, str):
            tags = (tags,)
        radius = max(0, min(int(radius), int((x1 - x0) / 2), int((y1 - y0) / 2)))
        if radius <= 0:
            self.create_rectangle(x0, y0, x1, y1, fill="", tags=tags, **common)
            return

        arc_opts = common.copy()
        arc_opts["style"] = "arc"

        self.create_arc(x0, y0, x0 + 2 * radius, y0 + 2 * radius, start=90, extent=90, tags=tags, **arc_opts)
        self.create_arc(x1 - 2 * radius, y0, x1, y0 + 2 * radius, start=0, extent=90, tags=tags, **arc_opts)
        self.create_arc(x1 - 2 * radius, y1 - 2 * radius, x1, y1, start=270, extent=90, tags=tags, **arc_opts)
        self.create_arc(x0, y1 - 2 * radius, x0 + 2 * radius, y1, start=180, extent=90, tags=tags, **arc_opts)
        line_opts = common.copy()
        line_opts.pop("style", None)
        outline_color = line_opts.pop("outline", None)
        if outline_color is not None:
            line_opts.setdefault("fill", outline_color)
        self.create_line(x0 + radius, y0, x1 - radius, y0, tags=tags, **line_opts)
        self.create_line(x1, y0 + radius, x1, y1 - radius, tags=tags, **line_opts)
        self.create_line(x0 + radius, y1, x1 - radius, y1, tags=tags, **line_opts)
        self.create_line(x0, y0 + radius, x0, y1 - radius, tags=tags, **line_opts)

    # ------------------------------------------------------------------
    def _on_enter(self, _event: tk.Event) -> None:
        self._hover = True
        self._schedule_tooltip()
        self._render()

    def _on_leave(self, _event: tk.Event) -> None:
        self._hover = False
        if not self._pressed:
            self._cancel_tooltip()
        self._render()

    def _on_press(self, _event: tk.Event) -> None:
        self.focus_set()
        self._pressed = True
        self._cancel_tooltip()
        self._render()

    def _on_release(self, event: tk.Event) -> None:
        was_pressed = self._pressed
        self._pressed = False
        self._render()
        if was_pressed and self._inside(event.x, event.y):
            self._invoke()

    def _on_key_activate(self, _event: tk.Event) -> None:
        self._invoke()

    def _on_focus_in(self, _event: tk.Event) -> None:
        self._focused = True
        self._render()

    def _on_focus_out(self, _event: tk.Event) -> None:
        self._focused = False
        self._cancel_tooltip()
        self._render()

    def _on_configure(self, _event: tk.Event) -> None:
        self.after_idle(self._render)

    # ------------------------------------------------------------------
    def _invoke(self) -> None:
        if callable(self._command):
            try:
                self._command()
            except Exception:
                LOGGER.exception("NeoGhostButton command failed")

    def _inside(self, x: float, y: float) -> bool:
        return 0 <= x <= self.winfo_width() and 0 <= y <= self.winfo_height()

    def _schedule_tooltip(self) -> None:
        if not self._tooltip_text:
            return
        if self._tooltip_window is not None or self._tooltip_after is not None:
            return
        self._tooltip_after = self.after(450, self._show_tooltip)

    def _show_tooltip(self) -> None:
        self._tooltip_after = None
        if not self._tooltip_text or not self.winfo_ismapped():
            return
        if self._tooltip_window is not None:
            return
        try:
            toplevel = tk.Toplevel(self)
            toplevel.overrideredirect(True)
        except Exception:
            return
        toplevel.configure(bg=theme_holo.PALETTE.get("surface_hi", theme_holo.COLOR_SURFACE_HI))
        try:
            toplevel.attributes("-topmost", True)
        except Exception:
            pass

        label = tk.Label(
            toplevel,
            text=self._tooltip_text,
            bg=toplevel.cget("bg"),
            fg=theme_holo.PALETTE.get("text", theme_holo.COLOR_TEXT),
            font=theme_holo.FONT_BODY,
            padx=8,
            pady=4,
        )
        label.pack()
        toplevel.update_idletasks()

        x = self.winfo_rootx() + (self.winfo_width() // 2) - (toplevel.winfo_width() // 2)
        y = self.winfo_rooty() + self.winfo_height() + 10
        toplevel.geometry(f"+{max(int(x), 0)}+{max(int(y), 0)}")
        self._tooltip_window = toplevel

    def _cancel_tooltip(self) -> None:
        if self._tooltip_after is not None:
            try:
                self.after_cancel(self._tooltip_after)
            except Exception:
                pass
            self._tooltip_after = None
        if self._tooltip_window is not None:
            try:
                self._tooltip_window.destroy()
            except Exception:
                pass
            self._tooltip_window = None

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


class TimerPopup(tk.Toplevel):
    """Modal timer selector with holographic keypad controls."""

    def __init__(
        self,
        master: tk.Misc | None = None,
        *,
        initial_seconds: int = 0,
        on_accept: Optional[Callable[[int], None]] = None,
    ) -> None:
        super().__init__(master)
        self.withdraw()
        self.overrideredirect(True)
        self.transient(master)
        self.configure(bg=theme_holo.COLOR_BG)

        self._on_accept = on_accept
        self._minutes_digits: list[str] = []
        self._seconds_digits: list[str] = []
        self._active_section: str = "seconds"
        self._message_var = tk.StringVar(value="")
        self._display_var = tk.StringVar(value="00:00")

        theme_holo.apply_holo_theme(self)

        self._initialise_digits(max(0, int(initial_seconds)))
        self._message_var.set("Marcando minutos" if self._active_section == "minutes" else "Marcando segundos")

        container = ttk.Frame(self, padding=24)
        container.pack(fill="both", expand=True)
        theme_holo.paint_grid_background(container)

        header = ttk.Label(container, text="Duración del temporizador", style="Header.TLabel")
        header.pack(pady=(0, 12))

        mono_font = getattr(theme_holo, "FONT_MONO_LG", ("DejaVu Sans Mono", 36, "bold"))
        display = ttk.Label(
            container,
            textvariable=self._display_var,
            anchor="center",
            font=mono_font,
            style="Header.TLabel",
        )
        display.pack(fill="x", pady=(0, 16))

        message = ttk.Label(
            container,
            textvariable=self._message_var,
            foreground=theme_holo.COLOR_ACCENT,
            style="Subheader.TLabel",
        )
        message.pack(pady=(0, 8))

        keypad = ttk.Frame(container)
        keypad.pack(fill="both", expand=True)

        keypad.columnconfigure((0, 1, 2), weight=1, uniform="keypad")

        rows = [
            ("7", "8", "9"),
            ("4", "5", "6"),
            ("1", "2", "3"),
            ("00", "0", ":"),
        ]
        for r_index, row in enumerate(rows):
            for c_index, label in enumerate(row):
                if label == ":":
                    command = self._toggle_section
                elif label == "00":
                    command = lambda value="00": self._append_value(value)
                else:
                    command = lambda value=label: self._append_value(value)
                ttk.Button(keypad, text=label, style="Accent.TButton", command=command).grid(
                    row=r_index,
                    column=c_index,
                    padx=4,
                    pady=4,
                    sticky="nsew",
                )

        actions = ttk.Frame(container)
        actions.pack(fill="x", pady=(12, 0))

        ttk.Button(actions, text="Borrar", style="Accent.TButton", command=lambda: self._handle_backspace(None)).pack(
            side="left", expand=True, fill="x", padx=(0, 6)
        )
        ttk.Button(actions, text="Cancelar", style="Accent.TButton", command=self._handle_cancel).pack(
            side="left", expand=True, fill="x", padx=3
        )
        ttk.Button(actions, text="Aceptar", style="Primary.TButton", command=self._handle_accept).pack(
            side="left", expand=True, fill="x", padx=(6, 0)
        )

        self.update_idletasks()
        self._center_on_master()
        self.deiconify()
        try:
            self.grab_set()
        except Exception:
            pass
        self.focus_force()

        self.bind("<Return>", self._on_return)
        self.bind("<KP_Enter>", self._on_return)
        self.bind("<Escape>", self._on_escape)
        self.bind("<BackSpace>", self._on_backspace)
        self.bind("<Control-BackSpace>", self._on_clear)

        self.protocol("WM_DELETE_WINDOW", self._handle_cancel)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _initialise_digits(self, initial_seconds: int) -> None:
        minutes = initial_seconds // 60
        seconds = initial_seconds % 60

        if minutes > 0:
            self._minutes_digits = list(str(minutes))
            self._active_section = "minutes"
        else:
            self._minutes_digits = []
            self._active_section = "seconds"

        if seconds > 0:
            self._seconds_digits = list(f"{seconds:02d}")
        else:
            self._seconds_digits = []

        self._update_display()

    def _toggle_section(self) -> None:
        self._active_section = "minutes" if self._active_section == "seconds" else "seconds"
        hint = "Marcando minutos" if self._active_section == "minutes" else "Marcando segundos"
        self._message_var.set(hint)

    def _append_value(self, value: str) -> None:
        self._message_var.set("")
        for char in value:
            self._append_digit(char)
        self._update_display()

    def _append_digit(self, digit: str) -> None:
        if digit not in "0123456789":
            return
        if self._active_section == "seconds":
            target = self._seconds_digits
            if len(target) >= 2:
                target.pop(0)
            target.append(digit)
            if len(target) == 2 and int("".join(target)) > 59:
                target.pop()
                self._message_var.set("Los segundos deben estar entre 0 y 59")
        else:
            target = self._minutes_digits
            if len(target) >= 4:
                return
            if len(target) == 1 and target[0] == "0":
                target[0] = digit
            else:
                target.append(digit)

    def _handle_clear(self) -> None:
        self._minutes_digits.clear()
        self._seconds_digits.clear()
        self._active_section = "seconds"
        self._message_var.set("")
        self._update_display()

    def _handle_backspace(self, _event: tk.Event | None = None) -> None:
        self._message_var.set("")
        if self._active_section == "seconds":
            if self._seconds_digits:
                self._seconds_digits.pop()
            else:
                self._active_section = "minutes"
                if self._minutes_digits:
                    self._minutes_digits.pop()
        else:
            if self._minutes_digits:
                self._minutes_digits.pop()
            else:
                self._active_section = "seconds"
                if self._seconds_digits:
                    self._seconds_digits.pop()
        self._update_display()

    def _handle_cancel(self) -> None:
        self._release_and_close()

    def _handle_accept(self) -> None:
        minutes = int("".join(self._minutes_digits)) if self._minutes_digits else 0
        seconds = int("".join(self._seconds_digits)) if self._seconds_digits else 0
        if seconds >= 60:
            self._message_var.set("Los segundos deben estar entre 0 y 59")
            return
        total = minutes * 60 + seconds
        if self._on_accept:
            try:
                self._on_accept(total)
            except Exception:
                pass
        self._release_and_close()

    def _update_display(self) -> None:
        minutes = int("".join(self._minutes_digits)) if self._minutes_digits else 0
        seconds = int("".join(self._seconds_digits)) if self._seconds_digits else 0
        seconds = max(0, min(seconds, 59))
        self._display_var.set(f"{minutes:02d}:{seconds:02d}")

    def _center_on_master(self) -> None:
        try:
            self.update_idletasks()
            width = self.winfo_width()
            height = self.winfo_height()
        except Exception:
            return

        master = self.master if isinstance(self.master, tk.Misc) else None
        if master is not None:
            try:
                master.update_idletasks()
                x = master.winfo_rootx() + (master.winfo_width() - width) // 2
                y = master.winfo_rooty() + (master.winfo_height() - height) // 2
            except Exception:
                x = (self.winfo_screenwidth() - width) // 2
                y = (self.winfo_screenheight() - height) // 2
        else:
            x = (self.winfo_screenwidth() - width) // 2
            y = (self.winfo_screenheight() - height) // 2

        self.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")

    def _release_and_close(self) -> None:
        try:
            self.grab_release()
        except Exception:
            pass
        self.destroy()

    # ------------------------------------------------------------------
    # Event bindings
    # ------------------------------------------------------------------
    def _on_return(self, _event: tk.Event | None = None) -> None:
        self._handle_accept()

    def _on_escape(self, _event: tk.Event | None = None) -> None:
        self._handle_cancel()

    def _on_backspace(self, event: tk.Event | None) -> None:  # noqa: D401 - Tk callback signature
        self._handle_backspace(event)

    def _on_clear(self, _event: tk.Event | None = None) -> None:
        self._handle_clear()

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
    "TimerPopup",
    "auto_apply_scaling",
    "apply_holo_tabs_style",
    "use_holo_notebook",
    "style_holo_checkbuttons",
    "apply_holo_theme_to_tree",
]

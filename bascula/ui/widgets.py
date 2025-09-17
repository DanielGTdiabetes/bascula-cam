"""Core visual components used across the Tk interface.

The original project evolved with a rather extensive widget toolkit that
included themed buttons, cards, toast notifications and a handful of helper
utilities tailored for touch devices.  During the simplification effort only a
very small subset remained which made most of the advanced screens unusable –
the modules still importing :mod:`bascula.ui.widgets` expected dozens of
attributes (``COL_BG``, ``Card``, ``Toast`` …) that simply were not present.

This module reintroduces those building blocks in a lightweight yet fully
functional manner.  The goal is not to recreate every single pixel of the old
design but to provide a consistent and modern look so that features such as the
settings tabs, Wi-Fi configurator or the scale overlay can render correctly.

The implementation deliberately favours clarity over extreme cleverness: most
widgets are regular ``tk.Frame``/``tk.Button`` subclasses with a couple of
convenience helpers.  Colours and font sizes are sourced from
``bascula.config.theme`` so switching themes continues to work as expected.
"""

from __future__ import annotations

import math
import os
import time
import tkinter as tk
from tkinter import ttk
from typing import Callable, Iterable, Optional

from bascula.config.theme import get_current_colors

try:  # Mascot palette stays in sync with theme when available
    from bascula.ui.widgets_mascota import refresh_palette as _mascot_refresh
except Exception:  # pragma: no cover - optional import
    _mascot_refresh = None

# ---------------------------------------------------------------------------
# Theme helpers

_UI_SCALE = float(os.environ.get("BASCULA_UI_SCALE", "1.0") or 1.0)


def _round(n: float) -> int:
    return int(round(n))


def get_scaled_size(value: int) -> int:
    """Return *value* scaled according to ``BASCULA_UI_SCALE``.

    On small displays (e.g. 800x480) the default scale of ``1.0`` keeps the UI
    sharp, while higher DPI panels can opt-in into slightly larger controls by
    exporting ``BASCULA_UI_SCALE=1.15``.
    """

    return _round(max(1, value * _UI_SCALE))


def refresh_theme_cache() -> None:
    """Update module level colour constants from the active theme."""

    global COLORS, COL_BG, COL_CARD, COL_CARD_HOVER, COL_BORDER, COL_TEXT
    global COL_MUTED, COL_ACCENT, COL_SUCCESS, COL_WARN, COL_DANGER, COL_SHADOW
    COLORS = get_current_colors()
    COL_BG = COLORS["COL_BG"]
    COL_CARD = COLORS["COL_CARD"]
    COL_CARD_HOVER = COLORS["COL_CARD_HOVER"]
    COL_BORDER = COLORS["COL_BORDER"]
    COL_TEXT = COLORS["COL_TEXT"]
    COL_MUTED = COLORS["COL_MUTED"]
    COL_ACCENT = COLORS["COL_ACCENT"]
    COL_SUCCESS = COLORS["COL_SUCCESS"]
    COL_WARN = COLORS["COL_WARN"]
    COL_DANGER = COLORS["COL_DANGER"]
    COL_SHADOW = COLORS.get("COL_SHADOW", "#00000033")
    if _mascot_refresh:
        try:
            _mascot_refresh()
        except Exception:
            pass


# Initialise constants at import time.
refresh_theme_cache()

# Touch friendly defaults
TOUCH_MIN_SIZE = get_scaled_size(46)
FS_TITLE = get_scaled_size(26)
FS_TEXT = get_scaled_size(14)
FS_BTN = get_scaled_size(16)
FS_BTN_SMALL = get_scaled_size(13)
FS_MONO = get_scaled_size(18)


# ---------------------------------------------------------------------------
# Basic containers & helpers

class Card(ttk.Frame):
    """Simple frame with the "card" background colour and rounded corners."""

    def __init__(self, parent: tk.Misc, **kwargs) -> None:
        style = kwargs.pop("style", "Card.TFrame")
        super().__init__(parent, style=style, padding=get_scaled_size(14), **kwargs)
        try:
            self.configure(borderwidth=0)
        except tk.TclError:
            pass
        self._apply_bg(self, COL_CARD)

    def _apply_bg(self, widget: tk.Misc, color: str) -> None:
        try:
            widget.configure(bg=color)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            self._apply_bg(child, color)


class WeightLabel(tk.Label):
    """Large numeric label used to display the weight on several screens."""

    def __init__(self, parent: tk.Misc, **kwargs) -> None:
        kwargs.setdefault("font", ("DejaVu Sans", get_scaled_size(72), "bold"))
        kwargs.setdefault("bg", COL_CARD)
        kwargs.setdefault("fg", COL_ACCENT)
        kwargs.setdefault("anchor", "e")
        super().__init__(parent, **kwargs)


class Mascot(tk.Canvas):
    """Tiny decorative mascot drawn using vector primitives."""

    def __init__(self, parent: tk.Misc, width: int = 60, height: int = 60, **kwargs) -> None:
        super().__init__(parent, width=width, height=height, highlightthickness=0, **kwargs)
        self.configure(bg=COL_CARD)
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        self.create_oval(6, 10, 54, 58, fill=COL_ACCENT, outline=COL_BORDER, width=2)
        self.create_oval(14, 4, 46, 36, fill=COL_ACCENT, outline=COL_BORDER, width=2)
        self.create_rectangle(22, 22, 38, 30, fill=COL_BG, outline=COL_BORDER, width=1)
        self.create_oval(22, 16, 28, 22, fill=COL_BG, outline=COL_BORDER, width=1)
        self.create_oval(36, 16, 42, 22, fill=COL_BG, outline=COL_BORDER, width=1)

    def refresh(self) -> None:
        self._draw()


def bind_touch_scroll(widget: tk.Misc, *, units_divisor: int = 4, min_drag_px: int = 6) -> None:
    """Enable drag-to-scroll behaviour on ``widget``.

    Tkinter treeviews and canvases are notoriously difficult to use on touch
    panels because the default scroll wheel bindings expect a mouse.  This
    helper attaches a very small gesture recogniser so the user can drag the
    content with a finger or stylus.
    """

    if not hasattr(widget, "yview"):
        return

    state = {"y": 0, "drag": False}

    def _start(event):
        state["y"] = event.y
        state["drag"] = False

    def _drag(event):
        delta = event.y - state["y"]
        if abs(delta) < min_drag_px:
            return
        state["drag"] = True
        state["y"] = event.y
        lines = int(delta / units_divisor)
        if lines:
            widget.yview_scroll(-lines, "units")

    def _stop(_event):
        state["drag"] = False

    widget.bind("<ButtonPress-1>", _start, add=True)
    widget.bind("<B1-Motion>", _drag, add=True)
    widget.bind("<ButtonRelease-1>", _stop, add=True)


def bind_text_entry(entry: tk.Entry) -> None:  # pragma: no cover - UI helper
    entry.configure(insertbackground=COL_ACCENT, fg=COL_TEXT, bg=COL_CARD_HOVER, relief="flat")


def bind_password_entry(entry: tk.Entry) -> None:  # pragma: no cover - UI helper
    bind_text_entry(entry)


# ---------------------------------------------------------------------------
# Buttons

class _BaseButton(tk.Button):
    def __init__(self, parent: tk.Misc, *, bg: str, fg: str, font, **kwargs) -> None:
        kwargs.setdefault("activebackground", COL_CARD_HOVER)
        kwargs.setdefault("activeforeground", fg)
        kwargs.setdefault("bd", 0)
        kwargs.setdefault("relief", "flat")
        kwargs.setdefault("cursor", "hand2")
        kwargs.setdefault("highlightthickness", 0)
        kwargs.setdefault("font", font)
        super().__init__(parent, bg=bg, fg=fg, **kwargs)
        self.configure(padx=get_scaled_size(14), pady=get_scaled_size(8))


class BigButton(_BaseButton):
    """Primary action button used across the UI."""

    def __init__(self, parent: tk.Misc, micro: bool = False, **kwargs) -> None:
        font = ("DejaVu Sans", FS_BTN_SMALL if micro else FS_BTN, "bold")
        super().__init__(parent, bg=COL_ACCENT, fg=COL_BG, font=font, **kwargs)


class GhostButton(_BaseButton):
    """Secondary button with transparent background."""

    def __init__(self, parent: tk.Misc, micro: bool = False, **kwargs) -> None:
        font = ("DejaVu Sans", FS_BTN_SMALL if micro else FS_BTN)
        super().__init__(parent, bg=COL_CARD, fg=COL_TEXT, font=font, **kwargs)
        self.configure(padx=get_scaled_size(10), pady=get_scaled_size(6))


# ---------------------------------------------------------------------------
# Toast notifications

class Toast:
    """Small transient message displayed on top of a widget."""

    def __init__(self, parent: tk.Misc) -> None:
        self.parent = parent
        self._label: Optional[tk.Label] = None
        self._hide_after: Optional[str] = None

    def show(self, text: str, timeout_ms: int = 1400, color: str = COL_ACCENT) -> None:
        if not text:
            return
        if self._label is None:
            self._label = tk.Label(
                self.parent,
                text=text,
                bg=color,
                fg=COL_BG,
                font=("DejaVu Sans", FS_TEXT, "bold"),
                padx=get_scaled_size(12),
                pady=get_scaled_size(8),
            )
        else:
            self._label.configure(text=text, bg=color)

        # Position near the bottom-right corner of the parent
        try:
            self._label.lift()
            self._label.place(relx=0.98, rely=0.98, anchor="se")
        except Exception:
            self._label.pack()  # fallback

        if self._hide_after:
            try:
                self.parent.after_cancel(self._hide_after)
            except Exception:
                pass

        def _hide() -> None:
            if self._label is not None:
                self._label.place_forget()

        self._hide_after = self.parent.after(timeout_ms, _hide)


# ---------------------------------------------------------------------------
# Keyboard popup (simplified)

class TextKeyPopup(tk.Toplevel):  # pragma: no cover - interactive widget
    """Very small on-screen keyboard for touch setups."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        title: str = "Introducir texto",
        initial: str = "",
        on_accept: Optional[Callable[[str], None]] = None,
        password: bool = False,
    ) -> None:
        super().__init__(parent)
        self.title(title)
        self.configure(bg=COL_BG)
        self.geometry("420x320")
        self.resizable(False, False)
        self.on_accept = on_accept

        self.var = tk.StringVar(value=initial)
        entry = tk.Entry(self, textvariable=self.var, show="*" if password else "")
        bind_text_entry(entry)
        entry.pack(fill="x", padx=16, pady=16)
        entry.focus_set()

        grid = tk.Frame(self, bg=COL_BG)
        grid.pack(fill="both", expand=True, padx=12)

        layout = [
            "1234567890",
            "qwertyuiop",
            "asdfghjkl",
            "zxcvbnm",
        ]

        def add_char(ch: str) -> None:
            entry.insert(tk.END, ch)

        for row, chars in enumerate(layout):
            row_frame = tk.Frame(grid, bg=COL_BG)
            row_frame.pack(pady=4)
            for ch in chars:
                BigButton(row_frame, text=ch, width=3, command=lambda c=ch: add_char(c), micro=True).pack(
                    side="left", padx=2
                )

        bottom = tk.Frame(self, bg=COL_BG)
        bottom.pack(fill="x", pady=12)
        GhostButton(bottom, text="Espacio", command=lambda: add_char(" "), micro=True).pack(side="left", padx=6)
        GhostButton(bottom, text="Borrar", command=lambda: entry.delete(len(entry.get()) - 1, tk.END), micro=True).pack(
            side="left", padx=6
        )
        BigButton(bottom, text="Aceptar", command=self._accept, micro=True).pack(side="right", padx=6)
        GhostButton(bottom, text="Cancelar", command=self.destroy, micro=True).pack(side="right", padx=6)

    def _accept(self) -> None:
        if callable(self.on_accept):
            self.on_accept(self.var.get())
        self.destroy()


# ---------------------------------------------------------------------------
# Top navigation bar

class TopBar(tk.Frame):
    """Navigation header with large touch targets and contextual menus."""

    _EXTRA_LABELS = [
        ("history", "Historial"),
        ("focus", "Enfoque"),
        ("nightscout", "Nightscout"),
        ("wifi", "Wi-Fi"),
        ("apikey", "API Key"),
        ("diabetes", "Diabetes"),
    ]

    def __init__(self, parent: tk.Misc, app) -> None:
        super().__init__(parent, bg=COL_CARD)
        self.app = app
        self._buttons: dict[str, tk.Button] = {}
        self._active_name = ""
        self._extra_entries: list[str] = []

        pad_x = max(get_scaled_size(16), TOUCH_MIN_SIZE // 2)
        pad_y = max(get_scaled_size(14), TOUCH_MIN_SIZE // 2)
        self._pad = (pad_x, pad_y)

        self.configure(padx=get_scaled_size(18), pady=get_scaled_size(10))

        left = tk.Frame(self, bg=COL_CARD)
        left.pack(side="left", fill="y")

        self.mascot = Mascot(left)
        self.mascot.pack(side="left", padx=(0, get_scaled_size(12)))
        try:
            self.mascot.bind("<Button-1>", lambda _e: self._on_mascot_tap())
        except Exception:
            pass

        self.title_lbl = tk.Label(
            left,
            text="Báscula Cam",
            bg=COL_CARD,
            fg=COL_TEXT,
            font=("DejaVu Sans", FS_TITLE, "bold"),
        )
        self.title_lbl.pack(side="left")

        center = tk.Frame(self, bg=COL_CARD)
        center.pack(side="left", fill="both", expand=True)

        self.weight_lbl = tk.Label(
            center,
            text="0 g",
            bg=COL_CARD,
            fg=COL_ACCENT,
            font=("DejaVu Sans", FS_TITLE, "bold"),
        )
        self.weight_lbl.pack(anchor="center")
        self._message_var = tk.StringVar(value="")
        self._message_after: Optional[str] = None
        self.message_lbl = tk.Label(
            center,
            textvariable=self._message_var,
            bg=COL_CARD,
            fg=COL_TEXT,
            font=("DejaVu Sans", FS_TEXT, "bold"),
        )
        self.message_lbl.pack_forget()

        right = tk.Frame(self, bg=COL_CARD)
        right.pack(side="right", fill="y")

        nav = tk.Frame(right, bg=COL_CARD)
        nav.pack(side="right")

        self._mic_var = tk.StringVar(value="Mic: OFF")
        self._mic_label = tk.Label(
            right,
            textvariable=self._mic_var,
            bg=COL_CARD,
            fg=COL_TEXT,
            font=("DejaVu Sans", max(FS_TEXT, get_scaled_size(14)), "bold"),
        )
        self._mic_label.pack(side="right", padx=(0, get_scaled_size(12)))

        nav_items = [
            ("home", "Inicio"),
            ("scale", "Pesar"),
            ("settings", "Ajustes"),
        ]
        for name, label in nav_items:
            btn = self._create_nav_button(nav, label, name)
            self._buttons[name] = btn

        self.recipe_btn = self._create_nav_button(nav, "Recetas", "recipes", command=self._open_recipes)

        self.more_btn = self._create_menu_button(nav, "Más ▾")
        self.more_menu = tk.Menu(
            self.more_btn,
            tearoff=0,
            bg=COL_CARD,
            fg=COL_TEXT,
            activebackground=COL_ACCENT,
            activeforeground=COL_BG,
        )
        self.more_btn.configure(menu=self.more_menu, state=tk.DISABLED)
        self.more_btn.bind("<ButtonRelease-1>", self._show_more_menu)

        self.admin_btn = self._create_menu_button(nav, "⋮ Admin")
        self.admin_menu = tk.Menu(
            self.admin_btn,
            tearoff=0,
            bg=COL_CARD,
            fg=COL_TEXT,
            activebackground=COL_ACCENT,
            activeforeground=COL_BG,
        )
        self.admin_btn.configure(menu=self.admin_menu)
        self.admin_btn.bind("<ButtonRelease-1>", self._show_admin_menu)
        self._build_admin_menu()

    def _create_nav_button(self, parent: tk.Misc, label: str, name: str, command=None) -> tk.Button:
        def _callback(s=name):
            if command is not None:
                try:
                    command()
                except Exception:
                    return
                self._after_navigation()
            else:
                self._on_nav_click(s)
        btn = tk.Button(
            parent,
            text=label,
            command=_callback,
            bg=COL_CARD,
            fg=COL_TEXT,
            activebackground=COL_ACCENT,
            activeforeground=COL_BG,
            font=("DejaVu Sans", max(FS_BTN, get_scaled_size(16)), "bold"),
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        btn.pack(side="left", padx=get_scaled_size(8))
        btn.configure(padx=self._pad[0], pady=self._pad[1])
        return btn

    def _create_menu_button(self, parent: tk.Misc, label: str) -> tk.Menubutton:
        btn = tk.Menubutton(
            parent,
            text=label,
            bg=COL_CARD,
            fg=COL_TEXT,
            activebackground=COL_ACCENT,
            activeforeground=COL_BG,
            font=("DejaVu Sans", max(FS_BTN, get_scaled_size(16)), "bold"),
            relief="flat",
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        btn.pack(side="left", padx=get_scaled_size(8))
        btn.configure(padx=self._pad[0], pady=self._pad[1])
        return btn

    def _on_nav_click(self, screen_name: str) -> None:
        try:
            self.app.show_screen(screen_name)
        except Exception:
            pass
        self._after_navigation()

    def _show_more_menu(self, _event) -> None:
        if not self._extra_entries or str(self.more_btn.cget("state")) == tk.DISABLED:
            return
        self._show_menu(self.more_btn, self.more_menu)

    def _show_admin_menu(self, _event) -> None:
        self._show_menu(self.admin_btn, self.admin_menu)

    def _show_menu(self, button: tk.Misc, menu: tk.Menu) -> None:
        try:
            x = button.winfo_rootx()
            y = button.winfo_rooty() + button.winfo_height()
            menu.tk_popup(x, y)
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass

    def _build_admin_menu(self) -> None:
        self.admin_menu.delete(0, tk.END)
        self.admin_menu.add_command(label="Inicio", command=lambda: self._on_nav_click("home"))
        self.admin_menu.add_separator()
        self.admin_menu.add_command(label="Salir", command=self._exit_app)

    def _open_recipes(self) -> None:
        try:
            self.app.open_recipes()
        except Exception:
            pass

    def _exit_app(self) -> None:
        try:
            self.app.root.destroy()
        except Exception:
            pass

    def _on_mascot_tap(self) -> None:
        try:
            if hasattr(self.mascot, "react"):
                self.mascot.react("tap")  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            if hasattr(self.app, "handle_mascot_tap"):
                self.app.handle_mascot_tap()
        except Exception:
            pass

    def set_active(self, name: str) -> None:
        canonical = self.app.resolve_screen_name(name) if hasattr(self.app, "resolve_screen_name") else name
        self._active_name = canonical
        self._update_active_styles()

    def _update_active_styles(self) -> None:
        for key, btn in self._buttons.items():
            if key == self._active_name:
                btn.configure(bg=COL_ACCENT, fg=COL_BG)
            else:
                btn.configure(bg=COL_CARD, fg=COL_TEXT)

        if self._active_name in self._extra_entries:
            self.more_btn.configure(bg=COL_ACCENT, fg=COL_BG)
        else:
            self.more_btn.configure(bg=COL_CARD, fg=COL_TEXT)
        try:
            if hasattr(self, "recipe_btn"):
                self.recipe_btn.configure(bg=COL_CARD, fg=COL_TEXT)
        except Exception:
            pass

    def update_weight(self, text: str, stable: bool) -> None:
        suffix = "✔" if stable else "…"
        self.weight_lbl.configure(text=f"{text} {suffix}")

    def set_message(self, text: str, *, timeout_ms: int = 2200) -> None:
        if self._message_after:
            try:
                self.after_cancel(self._message_after)
            except Exception:
                pass
            self._message_after = None

        text = (text or "").strip()
        if not text:
            self.clear_message()
            return

        self._message_var.set(text)
        try:
            if not self.message_lbl.winfo_ismapped():
                self.message_lbl.pack(anchor="center")
        except Exception:
            pass

        self._message_after = self.after(timeout_ms, self.clear_message)

    def clear_message(self) -> None:
        self._message_var.set("")
        try:
            self.message_lbl.pack_forget()
        except Exception:
            pass
        if self._message_after:
            try:
                self.after_cancel(self._message_after)
            except Exception:
                pass
            self._message_after = None

    def _after_navigation(self) -> None:
        mascot = getattr(self.app, "mascot_react", None)
        if callable(mascot):
            try:
                mascot("tap")
            except Exception:
                pass

    def set_mic_status(self, active: bool) -> None:
        text = "Mic: ON" if active else "Mic: OFF"
        color = COL_ACCENT if active else COL_TEXT
        self._mic_var.set(text)
        try:
            self._mic_label.configure(fg=color)
        except Exception:
            pass

    def filter_missing(self, screens: dict[str, tk.Frame]) -> None:
        self.more_menu.delete(0, tk.END)
        try:
            advanced = self.app.list_advanced_screens()
        except Exception:
            advanced = {}
        available: list[tuple[str, str]] = []
        seen: set[str] = set()
        for key, default in self._EXTRA_LABELS:
            if key in screens and key in advanced:
                available.append((key, advanced.get(key, default)))
                seen.add(key)
        for key, label in advanced.items():
            if key in screens and key not in seen:
                available.append((key, label))
        self._extra_entries = [key for key, _ in available]
        for key, label in available:
            self.more_menu.add_command(label=label, command=lambda s=key: self._on_nav_click(s))

        if self._extra_entries:
            self.more_btn.configure(state=tk.NORMAL, cursor="hand2")
        else:
            self.more_btn.configure(state=tk.DISABLED, cursor="")

        self._update_active_styles()


__all__ = [
    "Card",
    "Toast",
    "BigButton",
    "GhostButton",
    "WeightLabel",
    "TopBar",
    "Mascot",
    "TextKeyPopup",
    "bind_touch_scroll",
    "bind_text_entry",
    "bind_password_entry",
    "get_scaled_size",
    "TOUCH_MIN_SIZE",
    "FS_TITLE",
    "FS_TEXT",
    "FS_BTN",
    "FS_BTN_SMALL",
    "FS_MONO",
    "COL_BG",
    "COL_CARD",
    "COL_CARD_HOVER",
    "COL_BORDER",
    "COL_TEXT",
    "COL_MUTED",
    "COL_ACCENT",
    "COL_SUCCESS",
    "COL_WARN",
    "COL_DANGER",
    "COL_SHADOW",
]


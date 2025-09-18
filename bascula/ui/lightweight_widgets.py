"""Tiny widget helpers tuned for Raspberry Pi constraints."""
from __future__ import annotations

import logging
import tkinter as tk
from functools import lru_cache
from typing import Callable, Dict, Optional

from .rpi_config import TOUCH
from .theme_crt import CRT_COLORS, CRT_SPACING, draw_dotted_rule as theme_draw_dotted_rule, mono, safe_color, sans

logger = logging.getLogger("bascula.ui.widgets.lightweight")


def _safe_color(value: Optional[str], fallback: str = "#111111") -> str:
    if isinstance(value, str):
        value = value.strip()
        if value and value.lower() != "none":
            return value
    return fallback


class WidgetPool:
    """Recycles a small set of Tk widgets to avoid churn between screens."""

    def __init__(self, factory: Callable[[tk.Widget], tk.Widget]) -> None:
        self.factory = factory
        self._pool: Dict[int, list[tk.Widget]] = {}

    def acquire(self, parent: tk.Widget) -> tk.Widget:
        bucket = self._pool.setdefault(id(parent), [])
        try:
            widget = bucket.pop()
            return widget
        except IndexError:
            return self.factory(parent)

    def release(self, widget: tk.Widget) -> None:
        try:
            widget.pack_forget()
            widget.grid_forget()
        except Exception:
            pass
        parent = widget.master
        bucket = self._pool.setdefault(id(parent), [])
        bucket.append(widget)
class Card(tk.Frame):
    def __init__(self, parent: tk.Widget, **kwargs) -> None:
        bg = _safe_color(kwargs.pop("bg", CRT_COLORS.get("surface")))
        super().__init__(parent, bg=bg, highlightthickness=2, bd=0, highlightbackground=safe_color("divider"))
        self.configure(**kwargs)
        self._shadow = tk.Frame(parent, bg=CRT_COLORS["shadow"], bd=0, highlightthickness=0)
        self._shadow.place_forget()
        self.bind("<Map>", self._update_shadow, add=True)
        self.bind("<Configure>", self._update_shadow, add=True)

    def _update_shadow(self, _event=None) -> None:
        try:
            x = self.winfo_x() + 2
            y = self.winfo_y() + 4
            w = max(1, self.winfo_width())
            h = max(1, self.winfo_height())
            self._shadow.place(x=x, y=y, width=w, height=h)
        except Exception:
            pass

    def destroy(self) -> None:
        try:
            self._shadow.destroy()
        except Exception:
            pass
        super().destroy()


class CRTButton(tk.Button):
    """Large button with icon + label compliant with CRT spec."""

    def __init__(self, parent: tk.Widget, *, icon: str = "", text: str = "", **kwargs) -> None:
        padding = kwargs.pop("padding", CRT_SPACING.padding)
        min_height = kwargs.pop("min_height", 80)
        font = kwargs.pop("font", mono("sm"))
        accent = _safe_color(kwargs.pop("bg", CRT_COLORS.get("accent")), CRT_COLORS["accent"])
        accent_active = _safe_color(kwargs.pop("activebackground", CRT_COLORS.get("accent_dim")), CRT_COLORS["accent_dim"])
        fg_color = _safe_color(kwargs.pop("fg", CRT_COLORS.get("bg")), CRT_COLORS["bg"])
        display = icon if not text else f"{icon}\n{text}" if icon else text
        super().__init__(
            parent,
            text=display,
            bg=accent,
            fg=fg_color,
            activebackground=accent_active,
            activeforeground=fg_color,
            highlightthickness=2,
            highlightbackground=CRT_COLORS["accent_dark"],
            bd=0,
            relief="flat",
            font=font,
            padx=padding,
            pady=max(12, padding // 2),
        )
        for key, value in kwargs.items():
            try:
                self.configure(**{key: value})
            except Exception:
                logger.debug("No se pudo aplicar propiedad %s", key)
        self.after_idle(lambda: self._enforce_height(min_height))

    def _enforce_height(self, min_height: int) -> None:
        try:
            current = self.winfo_height()
            if current < min_height:
                extra = max(0, (min_height - current) // 2)
                self.configure(pady=self.cget("pady") + extra)
        except Exception:
            pass


# Backwards compatibility with older naming
AccentButton = CRTButton


class CRTToggle(tk.Frame):
    def __init__(self, parent: tk.Widget, *, text: str, command: Callable[[bool], None], initial: bool = False) -> None:
        super().__init__(parent, bg=CRT_COLORS["surface"])
        self._value = bool(initial)
        self._command = command
        self.columnconfigure(1, weight=1)
        self.indicator = tk.Canvas(self, width=72, height=40, bg=CRT_COLORS["surface"], highlightthickness=0, bd=0)
        self.indicator.grid(row=0, column=0, padx=(0, CRT_SPACING.padding))
        self.label = tk.Label(
            self,
            text=text,
            bg=CRT_COLORS["surface"],
            fg=CRT_COLORS["text"],
            font=sans("md", "bold"),
            anchor="w",
        )
        self.label.grid(row=0, column=1, sticky="ew")
        self.bind("<Button-1>", self._toggle, add=True)
        self.label.bind("<Button-1>", self._toggle, add=True)
        self.indicator.bind("<Button-1>", self._toggle, add=True)
        self._draw()

    def _draw(self) -> None:
        self.indicator.delete("all")
        radius = 18
        width = int(self.indicator.cget("width"))
        height = int(self.indicator.cget("height"))
        margin = 4
        track_color = CRT_COLORS["divider"]
        handle_color = CRT_COLORS["accent"] if self._value else CRT_COLORS["muted"]
        self.indicator.create_rectangle(margin, height // 2 - radius // 2, width - margin, height // 2 + radius // 2, fill=track_color, outline="")
        knob_x = width - margin - radius if self._value else margin
        self.indicator.create_oval(knob_x, height // 2 - radius, knob_x + radius * 2, height // 2 + radius, fill=handle_color, outline="")

    def _toggle(self, _event=None) -> None:
        self._value = not self._value
        self._draw()
        try:
            self._command(self._value)
        except Exception:
            logger.exception("Error ejecutando toggle %s", self.label.cget("text"))


class CRTTabBar(tk.Frame):
    def __init__(self, parent: tk.Widget, *, tabs: Dict[str, Callable[[], None]]) -> None:
        super().__init__(parent, bg=CRT_COLORS["surface"])
        self._buttons: Dict[str, tk.Button] = {}
        for index, (name, callback) in enumerate(tabs.items()):
            btn = tk.Button(
                self,
                text=name,
                bg=CRT_COLORS["surface"],
                fg=CRT_COLORS["muted"],
                activebackground=CRT_COLORS["surface_alt"],
                activeforeground=CRT_COLORS["text"],
                font=mono("xs"),
                highlightthickness=0,
                bd=0,
                padx=CRT_SPACING.padding,
                pady=12,
                command=callback,
            )
            btn.grid(row=0, column=index, padx=(0, CRT_SPACING.gutter))
            self._buttons[name] = btn

    def activate(self, name: str) -> None:
        for tab_name, button in self._buttons.items():
            active = tab_name == name
            try:
                button.configure(
                    fg=CRT_COLORS["text"] if active else CRT_COLORS["muted"],
                    bg=CRT_COLORS["surface_alt"] if active else CRT_COLORS["surface"],
                )
            except Exception:
                pass


class IconButton(CRTButton):
    def __init__(self, parent: tk.Widget, icon: str, text: str = "", **kwargs) -> None:
        super().__init__(parent, icon=icon, text=text, **kwargs)


class ValueLabel(tk.Label):
    def __init__(self, parent: tk.Widget, *, size_key: str = "xl", mono_font: bool = True, **kwargs) -> None:
        font_factory = mono if mono_font else sans
        font = kwargs.pop("font", font_factory(size_key, "bold"))
        super().__init__(
            parent,
            bg=_safe_color(kwargs.pop("bg", CRT_COLORS.get("surface"))),
            fg=_safe_color(kwargs.pop("fg", CRT_COLORS.get("text")), CRT_COLORS["text"]),
            font=font,
            padx=kwargs.pop("padx", CRT_SPACING.padding),
            pady=kwargs.pop("pady", 8),
        )
        self.configure(**kwargs)


class ScrollFrame(tk.Frame):
    """Scrollable area reusing a single Canvas instance."""

    def __init__(self, parent: tk.Widget, *, height: int = 320, width: int = 880) -> None:
        super().__init__(parent, bg=_safe_color(CRT_COLORS.get("bg")))
        self.canvas = tk.Canvas(
            self,
            bg=_safe_color(CRT_COLORS.get("bg")),
            highlightthickness=0,
            bd=0,
            width=width,
            height=height,
        )
        self.canvas.pack(side="left", fill="both", expand=True)
        self._inner = tk.Frame(self.canvas, bg=_safe_color(CRT_COLORS.get("bg")))
        self._window = self.canvas.create_window((0, 0), window=self._inner, anchor="nw")
        self._inner.bind("<Configure>", self._on_config)
        self.canvas.bind("<Configure>", self._on_canvas_config)
        self._scroll_id: Optional[str] = None

    @property
    def inner(self) -> tk.Frame:
        return self._inner

    def _on_config(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_config(self, event) -> None:
        self.canvas.itemconfigure(self._window, width=event.width)


@lru_cache(maxsize=32)
def lazy_color(name: str, fallback: str = "#222222") -> str:
    value = CRT_COLORS.get(name, fallback) or fallback
    if not value.startswith("#"):
        return fallback
    return value


def create_separator(parent: tk.Widget) -> tk.Frame:
    return tk.Frame(parent, bg=CRT_COLORS["divider"], height=2)


def format_weight(value: float) -> str:
    grams = float(value)
    unit = "g"
    if abs(grams) >= 1000:
        grams /= 1000.0
        unit = "kg"
    return f"{grams:0.1f} {unit}"


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


def draw_dotted_rule(canvas, x0: int, y0: int, x1: int, **kwargs) -> None:  # type: ignore[override]
    theme_draw_dotted_rule(canvas, x0, y0, x1, **kwargs)


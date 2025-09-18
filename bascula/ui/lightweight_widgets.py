"""Tiny widget helpers tuned for Raspberry Pi constraints."""
from __future__ import annotations

import logging
import tkinter as tk
from functools import lru_cache
from typing import Callable, Dict, Optional, Tuple

from .rpi_config import PRIMARY_COLORS, TOUCH, FONT_FAMILY, FONT_SIZES

logger = logging.getLogger("bascula.ui.widgets.lightweight")


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


def _base_font(size_key: str, weight: str = "normal") -> Tuple[str, int, str]:
    size = FONT_SIZES.get(size_key, FONT_SIZES["body"])
    return (FONT_FAMILY, size, weight)


class Card(tk.Frame):
    def __init__(self, parent: tk.Widget, **kwargs) -> None:
        bg = kwargs.pop("bg", PRIMARY_COLORS["surface"])
        super().__init__(parent, bg=bg, highlightthickness=0, bd=0)
        self.configure(**kwargs)
        self._shadow = tk.Frame(parent, bg=PRIMARY_COLORS["shadow"], bd=0, highlightthickness=0)
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


class AccentButton(tk.Button):
    def __init__(self, parent: tk.Widget, **kwargs) -> None:
        padding = kwargs.pop("padding", TOUCH.button_spacing)
        size = kwargs.pop("size", TOUCH.button_ideal)
        font = kwargs.pop("font", _base_font("body", "bold"))
        super().__init__(
            parent,
            bg=PRIMARY_COLORS["accent"],
            activebackground=PRIMARY_COLORS["accent_mid"],
            fg=PRIMARY_COLORS["bg"],
            activeforeground=PRIMARY_COLORS["bg"],
            highlightthickness=0,
            bd=0,
            relief="flat",
            font=font,
            padx=padding,
            pady=max(8, padding // 2),
        )
        min_w = kwargs.pop("min_width", TOUCH.button_min)
        self.configure(height=1, width=max(min_w // 10, 8))
        if size:
            self.configure(ipady=max(8, (size - TOUCH.button_min) // 2))
        for key, value in kwargs.items():
            try:
                self.configure(**{key: value})
            except Exception:
                logger.debug("No se pudo aplicar propiedad %s", key)


class IconButton(AccentButton):
    def __init__(self, parent: tk.Widget, icon: str, text: str = "", **kwargs) -> None:
        super().__init__(parent, **kwargs)
        display = f"{icon}\n{text}" if text else icon
        self.configure(text=display)


class ValueLabel(tk.Label):
    def __init__(self, parent: tk.Widget, *, size_key: str = "title", **kwargs) -> None:
        font = kwargs.pop("font", _base_font(size_key, "bold"))
        super().__init__(
            parent,
            bg=kwargs.pop("bg", PRIMARY_COLORS["surface"]),
            fg=kwargs.pop("fg", PRIMARY_COLORS["text"]),
            font=font,
            padx=kwargs.pop("padx", 12),
            pady=kwargs.pop("pady", 8),
        )
        self.configure(**kwargs)


class ScrollFrame(tk.Frame):
    """Scrollable area reusing a single Canvas instance."""

    def __init__(self, parent: tk.Widget, *, height: int = 320, width: int = 880) -> None:
        super().__init__(parent, bg=PRIMARY_COLORS["bg"])
        self.canvas = tk.Canvas(
            self,
            bg=PRIMARY_COLORS["bg"],
            highlightthickness=0,
            bd=0,
            width=width,
            height=height,
        )
        self.canvas.pack(side="left", fill="both", expand=True)
        self._inner = tk.Frame(self.canvas, bg=PRIMARY_COLORS["bg"])
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
    value = PRIMARY_COLORS.get(name, fallback) or fallback
    if not value.startswith("#"):
        return fallback
    return value


def create_separator(parent: tk.Widget) -> tk.Frame:
    return tk.Frame(parent, bg=PRIMARY_COLORS["accent_dark"], height=2)


def format_weight(value: float) -> str:
    grams = float(value)
    unit = "g"
    if abs(grams) >= 1000:
        grams /= 1000.0
        unit = "kg"
    return f"{grams:0.1f} {unit}"


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(value, maximum))


"""Reusable Tk widgets with conservative styling."""
from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk
from typing import Any, Callable, Iterable, Sequence

from .theme_classic import COLORS, SPACING, coerce_int, font, normalize_font, safe_color

logger = logging.getLogger("bascula.ui.widgets")


class _NormalizedWidget:
    """Mixin to coerce common Tk options to safe values."""

    def _consume_pad_options(self, kwargs: dict[str, Any]) -> tuple[int, int]:
        padx = coerce_int(kwargs.pop("padx", SPACING.padding), SPACING.padding)
        pady = coerce_int(kwargs.pop("pady", SPACING.padding // 2), SPACING.padding // 2)
        return padx, pady

    def _consume_size_options(self, kwargs: dict[str, Any]) -> tuple[int | None, int | None]:
        width = kwargs.pop("width", None)
        height = kwargs.pop("height", None)
        width_int = coerce_int(width, width) if isinstance(width, (int, float, str)) else None
        height_int = coerce_int(height, height) if isinstance(height, (int, float, str)) else None
        return width_int, height_int

    def _consume_font(self, kwargs: dict[str, Any], *, fallback: tuple[str, int, str]) -> tuple[Any, ...]:
        raw_font = kwargs.pop("font", fallback)
        normalized = normalize_font(raw_font, fallback)
        if isinstance(normalized, tuple):
            return normalized
        return tuple(normalized)


class ValueLabel(tk.Label, _NormalizedWidget):
    """Label that presents measurement values with consistent typography."""

    def __init__(self, parent: tk.Widget, *, text: str = "", size_key: str = "lg", mono_font: bool = False, **kwargs: Any) -> None:
        fallback = font(size_key, family="mono" if mono_font else "ui", weight="bold" if mono_font else "normal")
        normalized_font = self._consume_font(kwargs, fallback=fallback)
        fg = safe_color(kwargs.pop("fg", None), COLORS["text"])
        bg = safe_color(kwargs.pop("bg", None), COLORS["surface"])
        super().__init__(parent, text=text, font=normalized_font, fg=fg, bg=bg, anchor=kwargs.pop("anchor", "center"))
        for key, value in kwargs.items():
            try:
                self.configure(**{key: value})
            except tk.TclError:
                logger.warning("Ignoring unsupported option %s=%r for ValueLabel", key, value)


class PrimaryButton(tk.Button, _NormalizedWidget):
    """Prominent button used across the UI."""

    def __init__(self, parent: tk.Widget, *, text: str, command: Callable[[], None], **kwargs: Any) -> None:
        fallback = font("md", family="ui", weight="bold")
        normalized_font = self._consume_font(kwargs, fallback=fallback)
        padx, pady = self._consume_pad_options(kwargs)
        width, height = self._consume_size_options(kwargs)
        bg = safe_color(kwargs.pop("bg", None), COLORS["accent"])
        fg = safe_color(kwargs.pop("fg", None), COLORS["accent_fg"])
        activebackground = safe_color(kwargs.pop("activebackground", None), COLORS["accent_dim"])
        activeforeground = safe_color(kwargs.pop("activeforeground", None), COLORS["accent_fg"])
        super().__init__(
            parent,
            text=text,
            command=command,
            font=normalized_font,
            bg=bg,
            fg=fg,
            activebackground=activebackground,
            activeforeground=activeforeground,
            relief=tk.RAISED,
            padx=padx,
            pady=pady,
        )
        if width is not None:
            self.configure(width=width)
        if height is not None:
            self.configure(height=height)
        for key, value in kwargs.items():
            try:
                self.configure(**{key: value})
            except tk.TclError:
                logger.warning("Unsupported button option %s=%r", key, value)


class SecondaryButton(PrimaryButton):
    def __init__(self, parent: tk.Widget, *, text: str, command: Callable[[], None], **kwargs: Any) -> None:
        kwargs.setdefault("bg", COLORS["surface_alt"])
        kwargs.setdefault("fg", COLORS["text"])
        kwargs.setdefault("activebackground", COLORS["accent"])
        kwargs.setdefault("activeforeground", COLORS["accent_fg"])
        super().__init__(parent, text=text, command=command, **kwargs)


class TabBar(tk.Frame, _NormalizedWidget):
    """Simple horizontal tab selector."""

    def __init__(self, parent: tk.Widget, *, tabs: Sequence[str], command: Callable[[str], None]) -> None:
        super().__init__(parent, bg=COLORS["surface"])
        self._command = command
        self._buttons: dict[str, tk.Button] = {}
        for name in tabs:
            button = SecondaryButton(self, text=name, command=lambda value=name: self._trigger(value))
            button.pack(side=tk.LEFT, padx=SPACING.padding, pady=SPACING.padding)
            self._buttons[name] = button
        if tabs:
            self.select(tabs[0])

    def _trigger(self, value: str) -> None:
        self.select(value)
        self._command(value)

    def select(self, value: str) -> None:
        for name, button in self._buttons.items():
            if name == value:
                button.configure(relief=tk.SUNKEN)
            else:
                button.configure(relief=tk.RAISED)


class ScrollFrame(tk.Frame):
    """Scrollable frame using a canvas+window combination."""

    def __init__(self, parent: tk.Widget, *, width: int = 480, height: int = 320) -> None:
        super().__init__(parent, bg=COLORS["surface"])
        self.canvas = tk.Canvas(self, bg=COLORS["surface"], highlightthickness=0, width=width, height=height)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas, bg=COLORS["surface"])
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)


def format_weight(value: float) -> str:
    return f"{value:0.1f} g"


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


__all__ = [
    "ValueLabel",
    "PrimaryButton",
    "SecondaryButton",
    "TabBar",
    "ScrollFrame",
    "format_weight",
    "clamp",
]

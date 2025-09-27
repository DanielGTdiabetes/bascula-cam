"""Utility bindings for Tkinter inputs in touch-oriented screens."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

__all__ = [
    "bind_text_entry",
    "bind_password_entry",
    "bind_numeric_entry",
    "bind_touch_scroll",
]


def _select_all_on_focus(entry: tk.Entry) -> None:
    def _handler(_event: tk.Event) -> None:
        try:
            entry.select_range(0, "end")
        except Exception:
            pass

    entry.bind("<FocusIn>", _handler, add=True)


def bind_text_entry(entry: tk.Entry) -> None:
    """Improve UX for standard text entries on touch screens."""

    _select_all_on_focus(entry)



def bind_password_entry(entry: tk.Entry) -> None:
    """Same as :func:`bind_text_entry` but for password fields."""

    _select_all_on_focus(entry)


def bind_numeric_entry(entry: tk.Entry, *, decimals: int = 0) -> None:
    """Restrict the entry to numeric characters (optionally with decimals)."""

    allowed = {"-", ""}
    if decimals > 0:
        allowed.add(".")
    vcmd = entry.register(lambda value: _validate_numeric(value, decimals, allowed))
    entry.configure(validate="key", validatecommand=(vcmd, "%P"))
    _select_all_on_focus(entry)


def _validate_numeric(value: str, decimals: int, allowed: set[str]) -> bool:
    if value in allowed:
        return True
    if value.count("-") > 1:
        return False
    if value.startswith("-"):
        value = value[1:]
    if decimals == 0:
        return value.isdigit()
    try:
        float(value or "0")
        if value.count(".") <= 1:
            return all(ch.isdigit() or ch == "." for ch in value)
    except Exception:
        return False
    return False


def bind_touch_scroll(widget: tk.Misc, *, units_divisor: int = 4, min_drag_px: int = 4) -> None:
    """Enable drag based scrolling on list-like widgets."""

    if not hasattr(widget, "yview_scroll"):
        return

    state = {"y": None}

    def _on_press(event: tk.Event) -> None:
        state["y"] = event.y

    def _on_move(event: tk.Event) -> None:
        if state["y"] is None:
            return
        dy = event.y - state["y"]
        if abs(dy) < min_drag_px:
            return
        steps = int(-dy / max(1, units_divisor))
        if steps:
            try:
                widget.yview_scroll(steps, "units")
            except Exception:
                pass
            state["y"] = event.y

    def _on_release(_event: tk.Event) -> None:
        state["y"] = None

    widget.bind("<ButtonPress-1>", _on_press, add=True)
    widget.bind("<B1-Motion>", _on_move, add=True)
    widget.bind("<ButtonRelease-1>", _on_release, add=True)

    def _on_mousewheel(event: tk.Event) -> None:
        delta = 0
        if event.num == 4:
            delta = -1
        elif event.num == 5:
            delta = 1
        elif event.delta:
            delta = int(-event.delta / 120)
        if delta:
            try:
                widget.yview_scroll(delta, "units")
            except Exception:
                pass

    widget.bind("<MouseWheel>", _on_mousewheel, add=True)
    widget.bind("<Button-4>", _on_mousewheel, add=True)
    widget.bind("<Button-5>", _on_mousewheel, add=True)

"""Windowing helpers for configuring the Tk kiosk mode."""
from __future__ import annotations

import os
import tkinter as tk
from typing import Callable


_TRUE_VALUES = {"1", "true", "yes", "on"}


def _env_flag(name: str) -> bool:
    """Return ``True`` when the named environment variable is truthy."""

    return (os.environ.get(name) or "").strip().lower() in _TRUE_VALUES


def _safe_apply(call: Callable[..., object], *args: object) -> None:
    """Run ``call`` with ``args`` swallowing ``tk.TclError`` exceptions."""

    try:
        call(*args)
    except tk.TclError:
        pass


def _is_fullscreen(root: tk.Tk) -> bool:
    """Best-effort detection of the current fullscreen state."""

    for attr in ("attributes", "wm_attributes"):
        getter = getattr(root, attr, None)
        if getter is None:
            continue
        try:
            value = bool(getter("-fullscreen"))
        except tk.TclError:
            continue
        else:
            return value
    return False


def apply_kiosk_window_prefs(root: tk.Tk) -> None:
    """Configure ``root`` for the fullscreen/undecorated kiosk experience."""

    strict_mode = _env_flag("BASCULA_KIOSK_STRICT")
    debug_mode = _env_flag("BASCULA_DEBUG_KIOSK")

    width = max(1, int(getattr(root, "winfo_screenwidth", lambda: 0)() or 0))
    height = max(1, int(getattr(root, "winfo_screenheight", lambda: 0)() or 0))
    if width and height:
        root.geometry(f"{width}x{height}+0+0")

    def _set_fullscreen(enabled: bool) -> None:
        for attr in ("attributes", "wm_attributes"):
            setter = getattr(root, attr, None)
            if setter is None:
                continue
            _safe_apply(setter, "-fullscreen", enabled)
        if enabled:
            _safe_apply(root.state, "zoomed")
        else:
            _safe_apply(root.state, "normal")

    _set_fullscreen(True)
    _safe_apply(root.attributes, "-topmost", True)

    def _escape_override(_event: tk.Event) -> str:
        return "break"

    root.bind("<Escape>", _escape_override, add="+")

    if strict_mode:
        _safe_apply(root.overrideredirect, True)

    if debug_mode:

        def _toggle_fullscreen(_event: tk.Event | None = None) -> str:
            currently_fullscreen = _is_fullscreen(root)
            if currently_fullscreen and strict_mode:
                _safe_apply(root.overrideredirect, False)
            _set_fullscreen(not currently_fullscreen)
            if strict_mode and not currently_fullscreen:
                _safe_apply(root.overrideredirect, True)
            return "break"

        root.bind("<F11>", _toggle_fullscreen, add="+")


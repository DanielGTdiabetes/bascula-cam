"""Window helpers to keep the UI in kiosk mode."""
from __future__ import annotations

import logging
import os
import sys
import tkinter as tk

log = logging.getLogger(__name__)


def _flag(name: str) -> bool:
    return (os.environ.get(name) or "").strip() in {"1", "true", "yes", "on"}


def _set_attribute(window: tk.Misc, name: str, value: object) -> bool:
    try:
        window.attributes(name, value)
        return True
    except (tk.TclError, AttributeError) as exc:  # pragma: no cover - depends on WM
        log.debug("Attribute %s not supported: %s", name, exc)
        return False


def _get_attribute(window: tk.Misc, name: str) -> object | None:
    try:
        return window.attributes(name)
    except (tk.TclError, AttributeError):  # pragma: no cover - depends on WM
        return None


def _set_overrideredirect(window: tk.Misc, enabled: bool) -> bool:
    try:
        window.overrideredirect(enabled)
        return True
    except tk.TclError as exc:  # pragma: no cover - depends on WM
        log.debug("overrideredirect not supported: %s", exc)
        return False


def _get_overrideredirect(window: tk.Misc) -> bool | None:
    try:
        value = window.overrideredirect()
    except tk.TclError:  # pragma: no cover - depends on WM
        return None
    return bool(value)


def _maybe_zoom(window: tk.Misc) -> bool:
    try:
        window.state("zoomed")
        return True
    except (tk.TclError, AttributeError) as exc:
        log.debug("Window manager does not support zoomed state: %s", exc)
        return False


def apply_kiosk_window_prefs(root: tk.Tk) -> None:
    """Configure the Tk root window for kiosk operation."""

    strict = _flag("BASCULA_KIOSK_STRICT") or _flag("BASCULA_KIOSK_HARD")
    debug_flag = _flag("BASCULA_DEBUG_KIOSK")
    log.info(
        "Applying kiosk window prefs platform=%s strict=%s debug=%s",
        sys.platform,
        strict,
        debug_flag,
    )

    width = root.winfo_screenwidth()
    height = root.winfo_screenheight()
    root.geometry(f"{width}x{height}+0+0")

    _set_attribute(root, "-fullscreen", True)
    _set_attribute(root, "-topmost", True)

    if sys.platform.startswith("win"):
        _maybe_zoom(root)

    root.bind("<Escape>", lambda event: "break")

    if strict:
        _set_overrideredirect(root, True)
        root.after(200, lambda: _set_overrideredirect(root, True))

    log.info(
        "Kiosk prefs applied fullscreen=%s topmost=%s override=%s",
        _get_attribute(root, "-fullscreen"),
        _get_attribute(root, "-topmost"),
        _get_overrideredirect(root),
    )


def apply_kiosk_to_toplevel(window: tk.Toplevel) -> None:
    """Apply kiosk restrictions to secondary windows."""

    _set_attribute(window, "-topmost", True)

    if sys.platform.startswith("win"):
        _maybe_zoom(window)

    if _flag("BASCULA_KIOSK_STRICT") or _flag("BASCULA_KIOSK_HARD"):
        _set_overrideredirect(window, True)
        window.after(200, lambda: _set_overrideredirect(window, True))


__all__ = ["apply_kiosk_window_prefs", "apply_kiosk_to_toplevel"]

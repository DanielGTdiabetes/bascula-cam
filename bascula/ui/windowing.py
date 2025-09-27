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


def _set_overrideredirect(window: tk.Misc, enabled: bool) -> bool:
    try:
        window.overrideredirect(enabled)
        return True
    except tk.TclError as exc:  # pragma: no cover - depends on WM
        log.debug("overrideredirect not supported: %s", exc)
        return False


def _try_zoom_on_windows(window: tk.Misc) -> bool:
    """Attempt to put the window in zoomed state on Windows platforms."""

    if not sys.platform.startswith("win"):
        return False

    try:
        window.state("zoomed")
        return True
    except tk.TclError as exc:
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

    fullscreen_applied = _set_attribute(root, "-fullscreen", True)
    topmost_applied = _set_attribute(root, "-topmost", True)
    zoom_applied = _try_zoom_on_windows(root)

    root.bind("<Escape>", lambda event: "break")

    override_applied = False
    if strict:
        override_applied = _set_overrideredirect(root, True)
        root.after(200, lambda: _set_overrideredirect(root, True))

    log.info(
        "Kiosk prefs applied platform=%s fullscreen=%s topmost=%s zoomed=%s override=%s",
        sys.platform,
        fullscreen_applied,
        topmost_applied,
        zoom_applied,
        override_applied,
    )


def apply_kiosk_to_toplevel(window: tk.Toplevel) -> None:
    """Apply kiosk restrictions to secondary windows."""

    strict = _flag("BASCULA_KIOSK_STRICT") or _flag("BASCULA_KIOSK_HARD")

    topmost_applied = _set_attribute(window, "-topmost", True)
    zoom_applied = _try_zoom_on_windows(window)
    override_applied = False

    if strict:
        override_applied = _set_overrideredirect(window, True)
        window.after(200, lambda: _set_overrideredirect(window, True))

    log.info(
        "Toplevel kiosk prefs applied platform=%s topmost=%s zoomed=%s override=%s",
        sys.platform,
        topmost_applied,
        zoom_applied,
        override_applied,
    )


__all__ = ["apply_kiosk_window_prefs", "apply_kiosk_to_toplevel"]

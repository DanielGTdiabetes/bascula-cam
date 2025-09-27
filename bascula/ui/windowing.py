"""Window helpers to keep the UI in kiosk mode."""
from __future__ import annotations

import logging
import os
import tkinter as tk

log = logging.getLogger(__name__)


def _flag(name: str) -> bool:
    return (os.environ.get(name) or "").strip() in {"1", "true", "yes", "on"}


def apply_kiosk_window_prefs(root: tk.Tk) -> None:
    """Configure the Tk root window for kiosk operation."""

    width = root.winfo_screenwidth()
    height = root.winfo_screenheight()
    root.geometry(f"{width}x{height}+0+0")
    root.attributes("-fullscreen", True)
    root.attributes("-topmost", True)
    root.state("zoomed")
    root.bind("<Escape>", lambda event: "break")

    strict = _flag("BASCULA_KIOSK_STRICT") or _flag("BASCULA_KIOSK_HARD")
    if strict:
        root.overrideredirect(True)
        root.after(200, lambda: root.overrideredirect(True))
    log.info(
        "Kiosk prefs applied fullscreen=%s topmost=%s strict=%s",
        root.attributes("-fullscreen"),
        root.attributes("-topmost"),
        strict,
    )


def apply_kiosk_to_toplevel(window: tk.Toplevel) -> None:
    """Apply kiosk restrictions to secondary windows."""

    window.attributes("-topmost", True)
    if _flag("BASCULA_KIOSK_STRICT") or _flag("BASCULA_KIOSK_HARD"):
        window.overrideredirect(True)
        window.after(200, lambda: window.overrideredirect(True))


__all__ = ["apply_kiosk_window_prefs", "apply_kiosk_to_toplevel"]

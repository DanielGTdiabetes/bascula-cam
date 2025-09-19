"""Configuration helpers for the Raspberry Pi optimized UI."""
from __future__ import annotations

import logging
import os
import platform
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

from .theme_crt import set_font_preferences

logger = logging.getLogger("bascula.ui.rpi_config")

PRIMARY_COLORS: Dict[str, str] = {
    "bg": "#0A1F0F",
    "surface": "#0A1F0F",
    "accent": "#00FF88",
    "accent_mid": "#00CC66",
    "accent_dark": "#00CC66",
    "info": "#00CC66",
    "warning": "#00CC66",
    "error": "#00CC66",
    "text": "#00FF88",
    "muted": "#00CC66",
    "shadow": "#0A1F0F",
    "fallback": "#0A1F0F",
}

FONT_FAMILY = "JetBrains Mono"
FONT_SIZES = {
    "title": 30,
    "subtitle": 22,
    "body": 18,
    "small": 15,
}



def _format_font_option(family: str, size: int) -> str:
    clean = (family or "").strip()
    if not clean:
        clean = "TkDefaultFont"
    if " " in clean and not (clean.startswith("{") and clean.endswith("}")):
        clean = f"{{{clean}}}"
    try:
        size_int = int(size)
    except (TypeError, ValueError):
        size_int = int(FONT_SIZES.get("body", 18))
    return f"{clean} {size_int}"


def _available_fonts(root: tk.Misc) -> set[str]:
    if tkfont is None:
        return set()
    try:
        families = tkfont.families(root)  # type: ignore[arg-type]
    except Exception:
        return set()
    return {str(name).lower() for name in families}


def _choose_font(families: set[str], candidates: list[str], default: str) -> str:
    for candidate in candidates:
        candidate = (candidate or "").strip()
        if candidate and candidate.lower() in families:
            return candidate
    return default

WINDOW_GEOMETRY = "1024x600"


@dataclass(slots=True)
class TouchMetrics:
    button_min: int = 60
    button_ideal: int = 80
    button_spacing: int = 12


TOUCH = TouchMetrics()


def configure_root(root: tk.Tk) -> None:
    """Apply kiosk-friendly defaults to the Tk root window."""
    bg = PRIMARY_COLORS.get("bg", "#0A1F0F") or "#0A1F0F"
    try:
        root.configure(bg=bg)
    except Exception:
        root.configure(bg="#0A1F0F")
    root.title("Báscula Cam")
    try:
        root.geometry(WINDOW_GEOMETRY)
    except Exception:
        pass
    try:
        root.attributes("-fullscreen", True)
    except Exception:
        root.attributes("-zoomed", True)
    families = _available_fonts(root)
    mono_candidates = [
        os.environ.get("BASCULA_FONT_MONO", ""),
        FONT_FAMILY,
        "DejaVu Sans Mono",
        "Liberation Mono",
        "FreeMono",
        "Monospace",
    ]
    sans_candidates = [
        os.environ.get("BASCULA_FONT_SANS", ""),
        "Fira Sans",
        "DejaVu Sans",
        "Liberation Sans",
        "Arial",
        "Sans",
    ]
    mono_family = _choose_font(families, mono_candidates, "TkFixedFont")
    sans_family = _choose_font(families, sans_candidates, "TkDefaultFont")
    set_font_preferences(mono=mono_family, sans=sans_family)
    font_option = _format_font_option(sans_family, FONT_SIZES["body"])
    try:
        root.option_add("*Font", font_option)
    except tk.TclError as exc:
        logger.warning("Falling back to TkDefaultFont for *Font option: %s", exc)
        root.option_add("*Font", _format_font_option("TkDefaultFont", FONT_SIZES["body"]))
    root.option_add("*Button.Padding", 12)
    root.option_add("*Button.Background", PRIMARY_COLORS["accent"])
    root.option_add("*Button.Foreground", PRIMARY_COLORS["bg"])


def detect_rpi() -> bool:
    """Best effort detection of Raspberry Pi hardware."""
    if os.environ.get("BASCULA_FORCE_RPI", "").strip():
        return True
    if platform.machine().startswith("arm") and Path("/proc/device-tree/model").exists():
        try:
            text = Path("/proc/device-tree/model").read_text(encoding="utf-8", errors="ignore")
            return "raspberry pi" in text.lower()
        except Exception:
            return False
    return False


GPU_MEM_HINTS: Dict[str, Tuple[int, int]] = {
    "rpi5": (512, 768),
}


def gpu_memory_hint() -> Tuple[int, int]:
    """Return soft GPU memory bounds for tuning previews."""
    model = "generic"
    if Path is not None:
        try:
            text = Path("/proc/device-tree/model").read_text(encoding="utf-8", errors="ignore")
            if "raspberry pi 5" in text.lower():
                model = "rpi5"
        except Exception:
            pass
    return GPU_MEM_HINTS.get(model, (256, 512))


def ensure_env_defaults() -> None:
    """Set environment defaults that make the UI more resilient."""
    os.environ.setdefault("BASCULA_PREVIEW_SIZE", "320x240")
    os.environ.setdefault("BASCULA_UI_TOUCH", "1")
    os.environ.setdefault("TK_USE_INPUT_METHODS", "0")


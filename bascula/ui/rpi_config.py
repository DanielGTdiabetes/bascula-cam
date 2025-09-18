"""Configuration helpers for the Raspberry Pi optimized UI."""
from __future__ import annotations

import logging
import os
import platform
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

logger = logging.getLogger("bascula.ui.rpi_config")

PRIMARY_COLORS: Dict[str, str] = {
    "bg": "#0B1F1A",
    "surface": "#123524",
    "accent": "#4ADE80",
    "accent_mid": "#22C55E",
    "accent_dark": "#16A34A",
    "info": "#22D3EE",
    "warning": "#EAB308",
    "error": "#EF4444",
    "text": "#F0FDF4",
    "muted": "#9CA3AF",
    "shadow": "#07130F",
    "fallback": "#111111",
}

FONT_FAMILY = "Inter"
FONT_SIZES = {
    "title": 30,
    "subtitle": 22,
    "body": 18,
    "small": 15,
}

WINDOW_GEOMETRY = "1024x600"


@dataclass(slots=True)
class TouchMetrics:
    button_min: int = 60
    button_ideal: int = 80
    button_spacing: int = 12


TOUCH = TouchMetrics()


def configure_root(root: tk.Tk) -> None:
    """Apply kiosk-friendly defaults to the Tk root window."""
    bg = PRIMARY_COLORS.get("bg", "#101010") or "#101010"
    try:
        root.configure(bg=bg)
    except Exception:
        root.configure(bg="#101010")
    root.title("Báscula Cam")
    try:
        root.geometry(WINDOW_GEOMETRY)
    except Exception:
        pass
    try:
        root.attributes("-fullscreen", True)
    except Exception:
        root.attributes("-zoomed", True)
    root.option_add("*Font", f"{FONT_FAMILY} {FONT_SIZES['body']}")
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


#!/usr/bin/env python3
"""Structural probe for the Tk UI without rendering a visible window."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, Iterable

os.environ.update(
    {
        "BASCULA_UI_DEV": "1",
        "BASCULA_UI_CURSOR": "0",
        "BASCULA_UI_FULLSCREEN": "1",
        "BASCULA_UI_THEME": os.environ.get("BASCULA_UI_THEME", "neo"),
        "BASCULA_UI_LIGHT": "1",
    }
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bascula.ui.app import BasculaAppTk  # noqa: E402
from bascula.ui.theme_neo import SPACING, wcag_contrast  # noqa: E402

REQUIRED_BUTTONS: Dict[str, str] = {
    "btn_tare": "Tara",
    "btn_swap": "g/ml",
    "btn_food": "Alimentos",
    "btn_recipe": "Recetas",
    "btn_timer": "Temporizador",
    "btn_settings": "Ajustes",
}

TOPBAR_WIDGETS: Iterable[str] = (
    "topbar_wifi",
    "topbar_speaker",
    "topbar_bg",
    "topbar_timer",
    "topbar_notif",
)


def as_int(value: int) -> int:
    return int(round(float(value)))


def normalize_padding(value: object) -> int:
    if isinstance(value, tuple):
        try:
            return min(as_int(v) for v in value)
        except Exception:
            return SPACING["sm"]
    try:
        return as_int(value)  # type: ignore[arg-type]
    except Exception:
        return SPACING["sm"]


def widget_size(widget) -> tuple[int, int]:
    width = widget.winfo_width() or widget.winfo_reqwidth()
    height = widget.winfo_height() or widget.winfo_reqheight()
    return as_int(width), as_int(height)


def dump_geometry(name: str, widget, root) -> Dict[str, int]:
    return {
        "name": name,
        "x": as_int(widget.winfo_rootx() - root.winfo_rootx()),
        "y": as_int(widget.winfo_rooty() - root.winfo_rooty()),
        "width": as_int(widget.winfo_width() or widget.winfo_reqwidth()),
        "height": as_int(widget.winfo_height() or widget.winfo_reqheight()),
    }


def main() -> int:
    errors: list[str] = []
    app = BasculaAppTk()
    try:
        root = app.root
        root.update_idletasks()
        root.update()

        width = root.winfo_width()
        height = root.winfo_height()
        if width != 1024 or height != 600:
            errors.append(f"Root window size expected 1024x600, got {width}x{height}")

        weight = app.ids.get("weight_display")
        if weight is None:
            errors.append("Missing weight_display widget")
        else:
            w_width, w_height = widget_size(weight)
            if w_height < int(0.25 * height):
                errors.append(
                    f"Weight display height too small: {w_height}px (expected >= {int(0.25 * height)})"
                )

        topbar = getattr(app.shell, "top_bar", None)
        if topbar is None:
            errors.append("Missing top bar frame")
        else:
            _, topbar_height = widget_size(topbar)
            if not 40 <= topbar_height <= 80:
                errors.append(
                    f"Top bar height out of range: {topbar_height}px (expected 40-80)"
                )

        geometry_dump: list[Dict[str, int]] = []
        if weight is not None:
            geometry_dump.append(dump_geometry("weight_display", weight, root))

        for name, label in REQUIRED_BUTTONS.items():
            widget = app.ids.get(name)
            if widget is None:
                errors.append(f"Missing button {name}")
                continue
            text = str(widget.cget("text"))
            image = str(widget.cget("image"))
            if text.strip() != label:
                errors.append(f"Button {name} text mismatch: {text!r} != {label!r}")
            if name != "btn_swap" and not image:
                errors.append(f"Button {name} is missing an icon image")
            btn_width, btn_height = widget_size(widget)
            if btn_height < 96:
                errors.append(f"Button {name} height too small: {btn_height}px < 96")
            if btn_width < 120:
                errors.append(f"Button {name} width too small: {btn_width}px < 120")
            grid_info = widget.grid_info()
            padding_x = normalize_padding(grid_info.get("padx", 0))
            padding_y = normalize_padding(grid_info.get("pady", 0))
            if padding_x < SPACING["sm"] or padding_y < SPACING["sm"]:
                errors.append(
                    f"Button {name} padding too small: padx={padding_x}, pady={padding_y}"
                )
            contrast = wcag_contrast(widget.cget("bg"), widget.cget("fg"))
            if contrast < 3.0:
                errors.append(
                    f"Contrast too low for {name}: {contrast} (expected >= 3.0)"
                )
            geometry_dump.append(dump_geometry(name, widget, root))

        for key in TOPBAR_WIDGETS:
            widget = app.ids.get(key)
            if widget is None:
                errors.append(f"Missing top bar widget {key}")
                continue
            geometry_dump.append(dump_geometry(key, widget, root))

        logs_dir = Path("ci-logs")
        logs_dir.mkdir(parents=True, exist_ok=True)
        (logs_dir / "ui_geometry.json").write_text(
            json.dumps(geometry_dump, indent=2),
            encoding="utf-8",
        )

    finally:
        try:
            app.destroy()
        except Exception:
            pass

    if errors:
        for message in errors:
            print(message, file=sys.stderr)
        return 1
    print("UI probe passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

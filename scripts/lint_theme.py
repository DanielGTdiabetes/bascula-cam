#!/usr/bin/env python3
"""Lint checks for the neo theme and required UI assets."""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(REPO_ROOT))

from bascula.ui import theme_neo as theme  # noqa: E402


def check_theme_constants() -> list[str]:
    errors: list[str] = []
    required_colors = {"bg", "fg", "accent", "muted", "danger"}
    missing_colors = sorted(required_colors - set(theme.COLORS))
    if missing_colors:
        errors.append(f"Missing COLORS keys: {', '.join(missing_colors)}")

    required_spacing = {"xs", "sm", "md", "lg", "xl"}
    missing_spacing = sorted(required_spacing - set(theme.SPACING))
    if missing_spacing:
        errors.append(f"Missing SPACING keys: {', '.join(missing_spacing)}")

    required_fonts = {"display", "h1", "h2", "body", "btn"}
    missing_fonts = sorted(required_fonts - set(theme.FONTS))
    if missing_fonts:
        errors.append(f"Missing FONTS keys: {', '.join(missing_fonts)}")

    contrast = theme.wcag_contrast(theme.COLORS["bg"], theme.COLORS["fg"])
    if contrast < 4.5:
        errors.append(f"Contrast ratio too low: {contrast}")
    return errors


def check_icons() -> list[str]:
    icons_dir = REPO_ROOT / "assets" / "icons"
    required_icons = [
        "tara.png",
        "cero.png",
        "swap.png",
        "food.png",
        "recipe.png",
        "timer.png",
        "settings.png",
    ]
    topbar_icons = [
        "wifi.png",
        "speaker.png",
        "bg.png",
        "alarm.png",
        "bell.png",
    ]
    errors: list[str] = []
    missing = [name for name in required_icons if not (icons_dir / name).exists()]
    if missing:
        errors.append("Missing action icons: " + ", ".join(sorted(missing)))
    missing_topbar = [
        name for name in topbar_icons if not (icons_dir / name).exists()
    ]
    if missing_topbar:
        errors.append("Missing topbar icons: " + ", ".join(sorted(missing_topbar)))
    return errors


def check_forbidden_imports() -> list[str]:
    pattern = re.compile(r"^\s*(?:from|import)\s+.*theme_crt")
    errors: list[str] = []
    for path in REPO_ROOT.rglob("*.py"):
        if path.name == "theme_crt.py":
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for lineno, line in enumerate(lines, start=1):
            if pattern.search(line):
                rel = path.relative_to(REPO_ROOT)
                errors.append(f"Forbidden import in {rel}:{lineno}: {line.strip()}")
    return errors


def main() -> int:
    errors: list[str] = []
    errors.extend(check_theme_constants())
    errors.extend(check_icons())
    errors.extend(check_forbidden_imports())

    if errors:
        for entry in errors:
            print(entry, file=sys.stderr)
        return 1
    print("theme lint passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

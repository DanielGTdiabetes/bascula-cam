#!/usr/bin/env python3
"""Smoke test that icon_loader can create Tk PhotoImage objects."""
from __future__ import annotations

import tkinter as tk

import pytest

from bascula.ui.icon_loader import load_icon


def test_load_icon_round_trip() -> None:
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - headless CI guard
        pytest.skip(f"Tk no disponible: {exc}")
    root.withdraw()
    try:
        icon = load_icon("tare.png", 96)
        assert icon.width() == 96
        assert icon.height() == 96
    finally:
        root.destroy()

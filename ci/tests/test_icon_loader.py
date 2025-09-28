#!/usr/bin/env python3
"""Smoke test that icon_loader can create Tk PhotoImage objects."""
from __future__ import annotations

import tkinter as tk

import pytest

from bascula.ui.icon_loader import load_icon


@pytest.fixture(scope="module")
def tk_root() -> tk.Tk:
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - headless CI guard
        pytest.skip(f"Tk no disponible: {exc}")
    root.withdraw()
    yield root
    root.destroy()


def test_load_icon_round_trip(tk_root: tk.Tk) -> None:
    icon = load_icon("tare.png", 72)
    assert icon.width() == 72
    assert icon.height() == 72
    assert load_icon("tare.png", 72) is icon


def test_load_icon_missing_returns_placeholder(tk_root: tk.Tk) -> None:
    placeholder = load_icon("__missing__.png", 64)
    assert placeholder.width() == 64
    assert placeholder.height() == 64


def test_load_icon_case_insensitive(tk_root: tk.Tk) -> None:
    icon = load_icon("TaRe", 48)
    assert icon.width() == 48
    assert icon.height() == 48

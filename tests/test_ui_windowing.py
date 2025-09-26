"""Tests for the Tkinter kiosk window configuration helpers."""
from __future__ import annotations

import os

import pytest


@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires X server")
def test_apply_kiosk_window_prefs() -> None:
    tkinter = pytest.importorskip("tkinter")

    from bascula.ui.windowing import apply_kiosk_window_prefs

    root = tkinter.Tk()
    try:
        apply_kiosk_window_prefs(root)
    finally:
        root.destroy()

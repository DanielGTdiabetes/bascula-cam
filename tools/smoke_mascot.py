#!/usr/bin/env python3
"""Smoke test for the lightweight mascot implementation."""
from __future__ import annotations

import logging
import sys
import tkinter as tk
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bascula.ui.app import BasculaAppTk
from bascula.ui.failsafe_mascot import MascotCanvas

LOG = logging.getLogger("bascula.tools.smoke_mascot")
logging.basicConfig(level=logging.INFO, format="%(message)s")


def exercise_show_message_defaults() -> None:
    class DummyApp(BasculaAppTk):  # type: ignore[misc]
        def __init__(self) -> None:
            pass

    dummy = DummyApp.__new__(DummyApp)  # type: ignore[misc]
    dummy.logger = LOG
    dummy.mascot_widget = None
    BasculaAppTk.show_mascot_message(dummy, "test", state="idle", icon=None, icon_color=None)  # type: ignore[arg-type]


def main() -> int:
    exercise_show_message_defaults()
    root = tk.Tk()
    root.title("Mascot smoke test")
    widget = MascotCanvas(root, width=280, height=240)
    widget.pack(expand=True, fill="both")
    for idx, state in enumerate(("idle", "listening", "processing", "happy", "error")):
        root.after(800 * idx, widget.configure_state, state)
    root.after(4800, root.destroy)
    root.mainloop()
    return 0


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    raise SystemExit(main())

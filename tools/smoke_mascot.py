"""Minimal smoke test for the mascot widget animations."""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from tkinter import Tk


# Ensure the repository root is on sys.path so ``bascula`` can be imported when
# this script is executed directly (e.g. ``python tools/smoke_mascot.py``).
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bascula.ui.app import BasculaAppTk
from bascula.ui.mascot import MascotWidget
from bascula.ui.mascot_messages import MascotMessenger


def _exercise_show_message_defaults() -> None:
    """Ensure ``show_mascot_message`` tolerates ``None`` icon inputs."""

    class _StubMessenger:
        def show(self, text: str, *, kind: str = "info", priority: int = 0, icon: str = "") -> None:
            """No-op stub used for smoke verification."""

    dummy = SimpleNamespace()
    dummy.logger = logging.getLogger("bascula.smoke_mascot")
    dummy.mascot_messenger = MascotMessenger(lambda: None, lambda: None)
    dummy.messenger = _StubMessenger()
    BasculaAppTk.show_mascot_message(dummy, "auto_captured", 42, icon=None, icon_color=None, ttl_ms=None)


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    _exercise_show_message_defaults()
    os.environ.setdefault("BASCULA_MASCOT_THEME", "retro-green")
    root = Tk()
    root.title("Mascot smoke test")
    widget = MascotWidget(root, max_width=260)
    widget.pack(expand=True, fill="both")
    widget.blink(True)
    widget.pulse(True)
    root.after(800, lambda: widget.set_state("listen"))
    root.after(1600, lambda: widget.set_state("think"))
    root.after(2400, lambda: widget.set_state("error"))
    root.after(3600, lambda: widget.set_state("sleep"))
    root.after(5000, lambda: widget.set_state("idle"))
    root.after(6500, root.destroy)
    root.mainloop()

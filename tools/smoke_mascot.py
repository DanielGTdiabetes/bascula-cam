"""Minimal smoke test for the mascot widget animations."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from tkinter import Tk


# Ensure the repository root is on sys.path so ``bascula`` can be imported when
# this script is executed directly (e.g. ``python tools/smoke_mascot.py``).
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bascula.ui.mascot import MascotWidget


if __name__ == "__main__":  # pragma: no cover - manual smoke test
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

"""Minimal smoke test for the mascot widget animations."""

from __future__ import annotations

import os
from tkinter import Tk

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

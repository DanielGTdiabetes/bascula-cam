"""Verificaciones básicas de la mascota en modo failsafe."""
from __future__ import annotations

import logging
import sys
import tkinter as tk
from contextlib import suppress
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bascula.ui.app import BasculaAppTk
from bascula.ui.failsafe_mascot import MascotCanvas, MascotPlaceholder

LOG = logging.getLogger("bascula.tools.smoke_mascot")
logging.basicConfig(level=logging.INFO, format="[smoke_mascot] %(message)s")


def exercise_message_defaults() -> None:
    class Dummy(BasculaAppTk):  # type: ignore[misc]
        def __init__(self) -> None:  # pragma: no cover - no se llama
            raise RuntimeError

    dummy = Dummy.__new__(Dummy)  # type: ignore[misc]
    dummy.logger = LOG
    dummy.mascot_widget = None
    dummy.root = None
    with suppress(Exception):
        BasculaAppTk.show_mascot_message(
            dummy,
            "mensaje",
            state="misterio",
            icon=None,
            icon_color=None,
        )  # type: ignore[arg-type]


def main() -> int:
    exercise_message_defaults()
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - entorno sin X
        LOG.warning("Tk no disponible: %s", exc)
        return 0
    root.withdraw()
    had_error = False
    try:
        try:
            widget = MascotCanvas(root, width=240, height=200)
        except Exception as exc:  # pragma: no cover - fallback
            LOG.warning("MascotCanvas no disponible: %s", exc)
            widget = MascotPlaceholder(root)
        states = ["idle", "listening", "processing", "happy", "error", "desconocido"]
        for state in states:
            try:
                widget.configure_state(state)  # type: ignore[attr-defined]
            except Exception as exc:  # pragma: no cover - diagnóstico
                LOG.error("Error configurando estado %s: %s", state, exc)
                had_error = True
        with suppress(Exception):
            widget.destroy()
    finally:
        with suppress(Exception):
            root.destroy()
    return 1 if had_error else 0


if __name__ == "__main__":
    sys.exit(main())

"""Entry point for the modern Báscula UI."""
from __future__ import annotations

import logging
import os
import sys
import tkinter as tk
from typing import Optional

from .app_shell import AppShell

log = logging.getLogger(__name__)


class BasculaAppTk:
    """Compatibility wrapper exposing the legacy API."""

    def __init__(self, root: Optional[tk.Tk] = None):
        self.shell = AppShell(root=root)

    @property
    def root(self) -> tk.Tk:
        return self.shell.root

    def run(self) -> None:
        self.shell.run()

    def cleanup(self) -> None:  # pragma: no cover - compatibility hook
        self.shell.destroy()


def smoke_test() -> str:
    """Return "ok" when the UI dependencies are available."""

    if not os.environ.get("DISPLAY"):
        return "ok"
    try:
        root = tk.Tk()
    except tk.TclError:
        return "ok"
    else:
        root.destroy()
        return "ok"


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point used by ``python -m bascula.ui.app``."""

    logging.basicConfig(level=logging.INFO)
    log.debug("Argumentos: %s", argv if argv is not None else sys.argv[1:])

    if not os.environ.get("DISPLAY"):
        log.error("DISPLAY no disponible; no se puede iniciar la UI moderna.")
        return 1

    try:
        app = AppShell()
    except tk.TclError as exc:
        log.error("No se pudo iniciar Tk: %s", exc)
        return 1

    try:
        app.run()
    finally:
        app.destroy()
    return 0


if __name__ == "__main__":  # pragma: no cover - module CLI
    sys.exit(main())

#!/usr/bin/env python3
"""Recorrido rápido de la navegación principal."""

from __future__ import annotations

import logging
import sys
import tkinter as tk
from contextlib import suppress

from bascula.ui.app import BasculaAppTk


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"[FAIL] Tk init: {exc}")
        return 1

    app = None
    try:
        app = BasculaAppTk(root=root)
    except Exception as exc:
        print(f"[FAIL] init: {exc}")
        with suppress(Exception):
            root.destroy()
        return 1

    visited = set()
    for name in list(app.screens.keys()):
        canonical = app.resolve_screen_name(name)
        if canonical in visited:
            continue
        visited.add(canonical)
        try:
            app.show_screen(canonical)
            app.root.update_idletasks()
            app.root.update()
        except Exception as exc:  # pragma: no cover - diagnóstico
            print(f"[FAIL] {canonical}: {exc}")
        else:
            print(f"[OK] {canonical}")

    with suppress(Exception):
        app.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

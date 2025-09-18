#!/usr/bin/env python3
"""Recorrido rápido de pantallas para detectar fallos de importación.

Se ejecuta sin bloquear la interfaz: crea la aplicación, recorre todas las
pantallas registradas y llama ``show_screen`` sobre cada una capturando
excepciones. El objetivo es verificar que ningún import opcional tumba la
navegación.
"""

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

    for name in list(app.screens.keys()):
        try:
            app.show_screen(name)
            app.root.update_idletasks()
            app.root.update()
        except Exception as exc:
            print(f"[FAIL] {name}: {exc}")
        else:
            print(f"[OK] {name}")

    with suppress(Exception):
        app.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

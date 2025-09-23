#!/usr/bin/env python3
"""Smoke test that icon_loader can create Tk PhotoImage objects."""
from __future__ import annotations

import tkinter as tk

from bascula.ui.icon_loader import load_icon


def main() -> None:
    root = tk.Tk()
    root.withdraw()
    try:
        icon = load_icon("save", 32)
        if icon is not None:
            assert icon.width() > 0 and icon.height() > 0
    finally:
        root.destroy()
    print("icon_loader ok")


if __name__ == "__main__":
    main()

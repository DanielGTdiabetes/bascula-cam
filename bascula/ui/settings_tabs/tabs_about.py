# -*- coding: utf-8 -*-
from __future__ import annotations

import tkinter as tk

from bascula.ui.widgets import COL_CARD, COL_TEXT
from bascula.ui.settings_tabs.utils import create_scrollable_tab


def _version_text() -> str:
    import subprocess, datetime, os
    try:
        here = os.path.dirname(__file__)
        root = here
        # git describe
        p = subprocess.run(["git", "describe", "--tags", "--always", "--dirty"], cwd=root, capture_output=True, text=True, timeout=4)
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.strip()
        p = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root, capture_output=True, text=True, timeout=4)
        if p.returncode == 0 and p.stdout.strip():
            return p.stdout.strip()
    except Exception:
        pass
    return "v0-" + datetime.datetime.now().strftime("%Y%m%d")


def add_tab(screen, notebook):
    inner = create_scrollable_tab(notebook, "Acerca de", padding=(16, 16))

    tk.Label(inner, text="Báscula Digital Pro", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 18, 'bold')).pack(pady=(0, 6))
    tk.Label(inner, text=f"Versión: {_version_text()}", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 12)).pack(anchor='w')
    tk.Label(inner, text="Ajustes modularizados", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 12)).pack(anchor='w', pady=(4,0))

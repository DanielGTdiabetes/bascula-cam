# -*- coding: utf-8 -*-
from __future__ import annotations

import tkinter as tk

from bascula.ui.widgets import COL_CARD, COL_TEXT


def add_tab(screen, notebook):
    tab = tk.Frame(notebook, bg=COL_CARD)
    notebook.add(tab, text="Acerca de")

    inner = tk.Frame(tab, bg=COL_CARD)
    inner.pack(fill="both", expand=True, padx=16, pady=16)

    tk.Label(inner, text="Báscula Digital Pro", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 18, 'bold')).pack(pady=(0, 6))
    tk.Label(inner, text="Ajustes modularizados", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 12)).pack()


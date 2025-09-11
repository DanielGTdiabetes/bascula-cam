# -*- coding: utf-8 -*-
from __future__ import annotations

import tkinter as tk

from bascula.ui.widgets import COL_CARD, COL_TEXT


def add_tab(screen, notebook):
    tab = tk.Frame(notebook, bg=COL_CARD)
    notebook.add(tab, text="Red")

    inner = tk.Frame(tab, bg=COL_CARD)
    inner.pack(fill="both", expand=True, padx=16, pady=12)

    ip = screen.get_current_ip()
    tk.Label(inner, text=f"IP local: {ip or 'No conectada'}", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 14)).pack(anchor='w')

    url = f"http://{ip or 'localhost'}:8080"
    tk.Label(inner, text=f"Panel Web: {url}", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 12)).pack(anchor='w', pady=(6, 0))

    fr = tk.Frame(inner, bg=COL_CARD)
    fr.pack(pady=12)
    tk.Button(fr, text="Configurar Wi‑Fi", command=lambda: screen.app.show_screen('wifi'), bg="#3b82f6", fg='white', bd=0, relief='flat', cursor='hand2').pack(side='left', padx=6)
    tk.Button(fr, text="API Key", command=lambda: screen.app.show_screen('apikey'), bg="#6b7280", fg='white', bd=0, relief='flat', cursor='hand2').pack(side='left', padx=6)


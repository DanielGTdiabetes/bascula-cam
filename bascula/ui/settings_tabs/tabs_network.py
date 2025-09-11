# -*- coding: utf-8 -*-
from __future__ import annotations

import tkinter as tk

from bascula.ui.widgets import COL_CARD, COL_TEXT, COL_ACCENT


def add_tab(screen, notebook):
    tab = tk.Frame(notebook, bg=COL_CARD)
    notebook.add(tab, text="Red")

    inner = tk.Frame(tab, bg=COL_CARD)
    inner.pack(fill="both", expand=True, padx=16, pady=12)

    ip_var = tk.StringVar(value=screen.get_current_ip() or 'No conectada')
    tk.Label(inner, textvariable=ip_var, bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 14)).pack(anchor='w')

    def url_text():
        ip = ip_var.get()
        base = ip if ip and ip != 'No conectada' else 'localhost'
        return f"Panel Web: http://{base}:8080"

    url_var = tk.StringVar(value=url_text())
    tk.Label(inner, textvariable=url_var, bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 12)).pack(anchor='w', pady=(6, 0))

    def on_refresh():
        ip = screen.get_current_ip() or 'No conectada'
        ip_var.set(ip)
        url_var.set(url_text())

    tk.Button(inner, text='Refrescar', command=on_refresh, bg=COL_ACCENT, fg='white', bd=0, relief='flat', cursor='hand2').pack(anchor='w', pady=6)

    fr = tk.Frame(inner, bg=COL_CARD)
    fr.pack(pady=12)
    tk.Button(fr, text="Configurar Wi‑Fi", command=lambda: screen.app.show_screen('wifi'), bg="#3b82f6", fg='white', bd=0, relief='flat', cursor='hand2').pack(side='left', padx=6)
    tk.Button(fr, text="API Key", command=lambda: screen.app.show_screen('apikey'), bg="#6b7280", fg='white', bd=0, relief='flat', cursor='hand2').pack(side='left', padx=6)

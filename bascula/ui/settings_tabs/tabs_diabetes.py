# -*- coding: utf-8 -*-
from __future__ import annotations

import tkinter as tk

from bascula.ui.widgets import COL_CARD, COL_TEXT, COL_ACCENT


def add_tab(screen, notebook):
    tab = tk.Frame(notebook, bg=COL_CARD)
    notebook.add(tab, text="Diabetes")

    inner = tk.Frame(tab, bg=COL_CARD)
    inner.pack(fill="both", expand=True, padx=16, pady=12)

    # Modo diabético
    fr = tk.Frame(inner, bg=COL_CARD)
    fr.pack(fill='x', pady=6)
    tk.Label(fr, text="Modo diabético (experimental):", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 14)).pack(side='left')
    var_dm = tk.BooleanVar(value=bool(screen.app.get_cfg().get('diabetic_mode', False)))

    def on_toggle_dm():
        try:
            cfg = screen.app.get_cfg(); cfg['diabetic_mode'] = bool(var_dm.get()); screen.app.save_cfg()
            btn_ns.config(state=('normal' if cfg['diabetic_mode'] else 'disabled'))
            screen.toast.show("Modo diabético: " + ("ON" if cfg['diabetic_mode'] else "OFF"), 900)
        except Exception:
            pass

    tk.Checkbutton(fr, text="Activado", variable=var_dm, command=on_toggle_dm, bg=COL_CARD, fg=COL_TEXT, selectcolor=COL_CARD).pack(side='left', padx=8)

    btn_ns = tk.Button(inner, text="Configurar Nightscout", command=lambda: screen.app.show_screen('nightscout'),
                       bg=COL_ACCENT, fg='white', bd=0, relief='flat', cursor='hand2')
    btn_ns.config(state=('normal' if var_dm.get() else 'disabled'))
    btn_ns.pack(pady=10)


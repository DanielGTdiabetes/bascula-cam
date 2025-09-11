# -*- coding: utf-8 -*-
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from bascula.ui.widgets import COL_CARD, COL_TEXT, COL_ACCENT


def add_tab(screen, notebook):
    tab = tk.Frame(notebook, bg=COL_CARD)
    notebook.add(tab, text="Báscula")

    inner = tk.Frame(tab, bg=COL_CARD)
    inner.pack(fill="both", expand=True, padx=16, pady=12)

    # Info de calibración actual
    info = tk.Frame(inner, bg=COL_CARD); info.pack(fill='x', pady=6)
    cf = float(screen.app.get_cfg().get('calib_factor', 1.0))
    tk.Label(info, text=f"Factor actual: {cf:.6f}", bg=COL_CARD, fg=COL_TEXT).pack(side='left', padx=(0,12))
    port = str(screen.app.get_cfg().get('port', '/dev/serial0'))
    tk.Label(info, text=f"Puerto serie: {port}", bg=COL_CARD, fg=COL_TEXT).pack(side='left')

    # Calibración
    tk.Button(inner, text="Iniciar Calibración", command=lambda: screen.app.show_screen('calib'),
              bg=COL_ACCENT, fg='white', bd=0, relief='flat', cursor='hand2',
              font=("DejaVu Sans", 14, 'bold')).pack(pady=8)

    # Suavizado
    fr = tk.Frame(inner, bg=COL_CARD)
    fr.pack(fill='x', pady=8)
    tk.Label(fr, text="Suavizado (muestras):", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 14)).pack(side='left')
    var_sm = tk.IntVar(value=int(screen.app.get_cfg().get('smoothing', 5)))
    lbl_val = tk.StringVar(value=str(var_sm.get()))

    def on_sm(_=None):
        try:
            v = max(1, min(50, int(var_sm.get())))
            cfg = screen.app.get_cfg(); cfg['smoothing'] = v; screen.app.save_cfg()
            lbl_val.set(str(v))
        except Exception:
            pass

    ttk.Scale(fr, from_=1, to=20, orient='horizontal', variable=var_sm, command=on_sm, length=220).pack(side='left', padx=10)
    tk.Label(fr, textvariable=lbl_val, bg=COL_CARD, fg=COL_TEXT).pack(side='left', padx=6)

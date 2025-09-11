# -*- coding: utf-8 -*-
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from bascula.ui.widgets import COL_CARD, COL_TEXT, COL_ACCENT


def add_tab(screen, notebook):
    tab = tk.Frame(notebook, bg=COL_CARD)
    notebook.add(tab, text="General")

    inner = tk.Frame(tab, bg=COL_CARD)
    inner.pack(fill="both", expand=True, padx=16, pady=12)

    # Sonido: toggle + probar
    row1 = tk.Frame(inner, bg=COL_CARD)
    row1.pack(fill="x", pady=6)
    tk.Label(row1, text="Sonido:", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 14)).pack(side="left")
    var_sound = tk.BooleanVar(value=bool(screen.app.get_cfg().get('sound_enabled', True)))

    def on_toggle_sound():
        try:
            cfg = screen.app.get_cfg(); cfg['sound_enabled'] = bool(var_sound.get()); screen.app.save_cfg()
            au = getattr(screen.app, 'get_audio', lambda: None)()
            if au:
                try: au.set_enabled(cfg['sound_enabled'])
                except Exception: pass
            screen.toast.show("Sonido: " + ("ON" if cfg['sound_enabled'] else "OFF"), 900)
        except Exception:
            pass

    ttk.Checkbutton(row1, text="Activado", variable=var_sound, command=on_toggle_sound).pack(side="left", padx=8)

    def on_test_sound():
        try:
            au = getattr(screen.app, 'get_audio', lambda: None)()
            if au:
                if bool(screen.app.get_cfg().get('sound_enabled', True)):
                    try: au.play_event('tare_ok')
                    except Exception: pass
                screen.toast.show("Prueba de sonido", 900)
            else:
                screen.toast.show("Audio no disponible", 1200)
        except Exception:
            pass

    tk.Button(row1, text="Probar", command=on_test_sound, bg=COL_ACCENT, fg='white', bd=0, relief='flat', cursor='hand2').pack(side='left', padx=8)

    # Wake Word
    row2 = tk.Frame(inner, bg=COL_CARD)
    row2.pack(fill="x", pady=6)
    tk.Label(row2, text="Wake Word:", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 14)).pack(side="left")
    var_ww = tk.BooleanVar(value=bool(screen.app.get_cfg().get('wakeword_enabled', False)))

    def on_toggle_ww():
        try:
            cfg = screen.app.get_cfg(); cfg['wakeword_enabled'] = bool(var_ww.get()); screen.app.save_cfg()
            screen.toast.show("Wake Word: " + ("ON" if cfg['wakeword_enabled'] else "OFF"), 900)
        except Exception:
            pass

    ttk.Checkbutton(row2, text="Activado", variable=var_ww, command=on_toggle_ww).pack(side="left", padx=8)


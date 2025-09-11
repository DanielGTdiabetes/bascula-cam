# -*- coding: utf-8 -*-
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from bascula.ui.widgets import (
    COL_CARD, COL_TEXT, COL_ACCENT, COL_CARD_HOVER,
    TouchScrollableFrame, bind_numeric_entry
)


def add_tab(screen, notebook):
    tab = tk.Frame(notebook, bg=COL_CARD)
    notebook.add(tab, text="General")

    sf = TouchScrollableFrame(tab, bg=COL_CARD)
    sf.pack(fill="both", expand=True, padx=16, pady=12)
    inner = sf.inner

    # Sonido: toggle + tema + probar
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

    tk.Label(row1, text="Tema:", bg=COL_CARD, fg=COL_TEXT).pack(side="left", padx=(12, 4))
    var_theme = tk.StringVar(value=str(screen.app.get_cfg().get('sound_theme', 'beep')))
    cb_theme = ttk.Combobox(row1, textvariable=var_theme, state='readonly', width=10, values=["beep", "voice_es"])
    cb_theme.pack(side='left')

    def on_theme_change(_e=None):
        try:
            theme = (var_theme.get() or 'beep').strip()
            cfg = screen.app.get_cfg(); cfg['sound_theme'] = theme; screen.app.save_cfg()
            au = getattr(screen.app, 'get_audio', lambda: None)()
            if au:
                # Probar update_config y, si existe, set_theme
                try:
                    au.update_config(cfg)
                except Exception:
                    try:
                        au.set_theme(theme)
                    except Exception:
                        pass
            screen.toast.show(f"Tema sonido: {theme}", 900)
        except Exception:
            pass

    cb_theme.bind("<<ComboboxSelected>>", on_theme_change)

    def on_test_sound():
        try:
            au = getattr(screen.app, 'get_audio', lambda: None)()
            if au:
                if bool(screen.app.get_cfg().get('sound_enabled', True)):
                    try: au.play_event('tare_ok')
                    except Exception: pass
                # Intentar un evento de voz
                try:
                    if hasattr(au, 'speak_event'): au.speak_event('announce_bg', n=123)
                except Exception:
                    pass
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

    # Piper model
    row_pm = tk.Frame(inner, bg=COL_CARD)
    row_pm.pack(fill='x', pady=6)
    tk.Label(row_pm, text="Modelo Piper (.onnx):", bg=COL_CARD, fg=COL_TEXT).pack(side='left')
    var_pm = tk.StringVar(value=str(screen.app.get_cfg().get('piper_model', '')))
    ent_pm = tk.Entry(row_pm, textvariable=var_pm, bg=COL_CARD_HOVER, fg=COL_TEXT, relief='flat', insertbackground=COL_TEXT, width=36)
    ent_pm.pack(side='left', padx=8)

    def on_save_pm():
        try:
            cfg = screen.app.get_cfg(); cfg['piper_model'] = (var_pm.get() or '').strip(); screen.app.save_cfg()
            au = getattr(screen.app, 'get_audio', lambda: None)()
            if au:
                try: au.update_config(cfg)
                except Exception: pass
            screen.toast.show('Modelo Piper actualizado', 900)
        except Exception:
            pass

    tk.Button(row_pm, text='Guardar', command=on_save_pm, bg=COL_ACCENT, fg='white', bd=0, relief='flat', cursor='hand2').pack(side='left')

    # Cámara: resolución foto comida
    row_cam = tk.Frame(inner, bg=COL_CARD)
    row_cam.pack(fill='x', pady=6)
    tk.Label(row_cam, text="Resolución foto comida:", bg=COL_CARD, fg=COL_TEXT).pack(side='left')
    cb_vals = ["4608x2592 (Alta)", "2304x1296 (Media)"]
    map_val = {cb_vals[0]: "4608x2592", cb_vals[1]: "2304x1296"}
    cur = str(screen.app.get_cfg().get('foodshot_size', '4608x2592'))
    var_cam = tk.StringVar(value=cb_vals[0] if cur.startswith('4608') else cb_vals[1])
    cb_cam = ttk.Combobox(row_cam, textvariable=var_cam, state='readonly', values=cb_vals, width=20)
    cb_cam.pack(side='left', padx=8)

    def on_apply_cam():
        try:
            val = map_val.get(var_cam.get(), '4608x2592')
            cfg = screen.app.get_cfg(); cfg['foodshot_size'] = val; screen.app.save_cfg()
            cam = getattr(screen.app, 'camera', None)
            if cam and hasattr(cam, 'set_profile_size'):
                w, h = [int(x) for x in val.split('x')]
                try: cam.set_profile_size('foodshot', (w, h))
                except Exception: pass
            screen.toast.show('Resolución actualizada', 900)
        except Exception:
            pass

    tk.Button(row_cam, text='Aplicar', command=on_apply_cam, bg=COL_ACCENT, fg='white', bd=0, relief='flat', cursor='hand2').pack(side='left')

    # Decimales
    row_dec = tk.Frame(inner, bg=COL_CARD)
    row_dec.pack(fill='x', pady=6)
    tk.Label(row_dec, text="Decimales en peso:", bg=COL_CARD, fg=COL_TEXT).pack(side='left')
    var_dec = tk.IntVar(value=int(screen.app.get_cfg().get('decimals', 0)))

    def on_apply_dec():
        try:
            cfg = screen.app.get_cfg(); cfg['decimals'] = int(var_dec.get()); screen.app.save_cfg()
            screen.toast.show(f"Decimales: {cfg['decimals']}", 900)
        except Exception:
            pass

    for i in (0, 1):
        ttk.Radiobutton(row_dec, text=str(i), variable=var_dec, value=i, command=on_apply_dec).pack(side='left', padx=4)


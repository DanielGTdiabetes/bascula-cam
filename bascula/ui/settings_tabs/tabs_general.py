# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk

from bascula.ui.widgets import (
    COL_CARD,
    COL_TEXT,
    COL_ACCENT,
    TouchScrollableFrame,
    bind_numeric_entry,
)
from bascula.services.llm_client import LLMClient


def add_tab(screen, notebook):
    tab = tk.Frame(notebook, bg=COL_CARD)
    notebook.add(tab, text="General")

    sf = TouchScrollableFrame(tab, bg=COL_CARD)
    sf.pack(fill="both", expand=True, padx=16, pady=12)
    inner = sf.inner

    # Modo Focus
    row_focus = tk.Frame(inner, bg=COL_CARD)
    row_focus.pack(fill='x', pady=6)
    tk.Label(row_focus, text="Modo Focus:", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 14)).pack(side='left')
    var_focus = tk.BooleanVar(value=bool(screen.app.get_cfg().get('focus_mode', True)))
    def on_toggle_focus():
        try:
            cfg = screen.app.get_cfg(); cfg['focus_mode'] = bool(var_focus.get()); screen.app.save_cfg()
            screen.toast.show("Focus: " + ("ON" if cfg['focus_mode'] else "OFF") + " (efecto al volver a Inicio)", 1200)
        except Exception:
            pass
    ttk.Checkbutton(row_focus, text="UI simplificada con overlays", variable=var_focus, command=on_toggle_focus).pack(side='left', padx=8)

    # Mascota
    row_masc = tk.Frame(inner, bg=COL_CARD)
    row_masc.pack(fill='x', pady=6)
    tk.Label(row_masc, text="Mascota:", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 14)).pack(side='left')

    var_person = tk.StringVar(value=str(screen.app.get_cfg().get('mascot_persona', 'discreto')))
    cb_person = ttk.Combobox(row_masc, textvariable=var_person, state='readonly', width=10,
                             values=['off', 'discreto', 'normal', 'jugueton'])
    cb_person.pack(side='left', padx=8)

    def on_person_change(_e=None):
        try:
            cfg = screen.app.get_cfg(); cfg['mascot_persona'] = var_person.get(); screen.app.save_cfg()
            screen.app.mascot_brain.personality = var_person.get()
            screen.toast.show('Personalidad actualizada', 900)
        except Exception:
            pass

    cb_person.bind("<<ComboboxSelected>>", on_person_change)

    row_limit = tk.Frame(inner, bg=COL_CARD)
    row_limit.pack(fill='x', pady=6)
    tk.Label(row_limit, text='Límite/hora:', bg=COL_CARD, fg=COL_TEXT).pack(side='left')
    var_lim = tk.IntVar(value=int(screen.app.get_cfg().get('mascot_max_per_hour', 3)))
    ent_lim = tk.Entry(row_limit, textvariable=var_lim, width=4)
    bind_numeric_entry(ent_lim)
    ent_lim.pack(side='left', padx=8)

    def on_save_lim():
        try:
            cfg = screen.app.get_cfg(); cfg['mascot_max_per_hour'] = int(var_lim.get()); screen.app.save_cfg()
            screen.app.mascot_brain.max_per_hour = int(var_lim.get())
            screen.toast.show('Límite guardado', 900)
        except Exception:
            pass

    tk.Button(row_limit, text='Guardar', command=on_save_lim, bg=COL_ACCENT, fg='white', bd=0, relief='flat', cursor='hand2').pack(side='left')

    row_nm = tk.Frame(inner, bg=COL_CARD)
    row_nm.pack(fill='x', pady=6)
    tk.Label(row_nm, text='No molestar:', bg=COL_CARD, fg=COL_TEXT).pack(side='left')
    var_nm = tk.BooleanVar(value=bool(screen.app.get_cfg().get('mascot_dnd', False)))

    def on_nm():
        try:
            cfg = screen.app.get_cfg(); cfg['mascot_dnd'] = bool(var_nm.get()); screen.app.save_cfg()
            screen.app.mascot_brain.no_disturb = bool(var_nm.get())
            screen.toast.show('No molestar: ' + ('ON' if cfg['mascot_dnd'] else 'OFF'), 900)
        except Exception:
            pass

    ttk.Checkbutton(row_nm, text='Activado', variable=var_nm, command=on_nm).pack(side='left', padx=8)

    row_llm = tk.Frame(inner, bg=COL_CARD)
    row_llm.pack(fill='x', pady=6)
    tk.Label(row_llm, text='LLM:', bg=COL_CARD, fg=COL_TEXT).pack(side='left')
    var_llm = tk.BooleanVar(value=bool(screen.app.get_cfg().get('mascot_llm_enabled', False)))

    def on_llm():
        try:
            cfg = screen.app.get_cfg(); cfg['mascot_llm_enabled'] = bool(var_llm.get()); screen.app.save_cfg()
            screen.app.mascot_brain.use_llm = bool(var_llm.get())
            screen.app.llm_client = LLMClient(screen.app.get_cfg().get('llm_api_key'))
            if cfg['mascot_llm_enabled']:
                screen.toast.show('Recuerda consentimiento para datos BG', 1600)
        except Exception:
            pass

    ttk.Checkbutton(row_llm, text='Activado', variable=var_llm, command=on_llm).pack(side='left', padx=8)

    var_sendbg = tk.BooleanVar(value=bool(screen.app.get_cfg().get('mascot_llm_send_health', False)))

    def on_sendbg():
        try:
            cfg = screen.app.get_cfg(); cfg['mascot_llm_send_health'] = bool(var_sendbg.get()); screen.app.save_cfg()
            screen.app.mascot_brain.allow_health = bool(var_sendbg.get())
        except Exception:
            pass

    ttk.Checkbutton(row_llm, text='Enviar BG', variable=var_sendbg, command=on_sendbg).pack(side='left', padx=8)

    row_key = tk.Frame(inner, bg=COL_CARD)
    row_key.pack(fill='x', pady=6)
    tk.Label(row_key, text='API Key:', bg=COL_CARD, fg=COL_TEXT).pack(side='left')
    var_key = tk.StringVar(value=str(screen.app.get_cfg().get('llm_api_key', '')))
    ent_key = tk.Entry(row_key, textvariable=var_key, width=24, show='*')
    ent_key.pack(side='left', padx=8)

    def on_save_key():
        try:
            cfg = screen.app.get_cfg(); cfg['llm_api_key'] = var_key.get().strip(); screen.app.save_cfg()
            screen.app.llm_client = LLMClient(var_key.get().strip())
            screen.toast.show('API Key guardada', 900)
        except Exception:
            pass

    tk.Button(row_key, text='Guardar', command=on_save_key, bg=COL_ACCENT, fg='white', bd=0,
              relief='flat', cursor='hand2').pack(side='left', padx=4)

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

    model_dirs = ["/opt/piper/models", "/usr/share/piper/voices"]
    models = []
    display = []
    for d in model_dirs:
        try:
            for fname in os.listdir(d):
                if fname.endswith('.onnx'):
                    models.append(fname)
                    display.append(fname[:-5])
        except FileNotFoundError:
            continue
    display_to_file = dict(zip(display, models))

    cur_file = os.path.basename(screen.app.get_cfg().get('piper_model', '') or '')
    cur_display = next((disp for disp, f in display_to_file.items() if f == cur_file), '')
    var_pm = tk.StringVar(value=cur_display)
    cb_pm = ttk.Combobox(row_pm, textvariable=var_pm, state='readonly', values=display, width=36)
    cb_pm.pack(side='left', padx=8)

    def on_save_pm():
        try:
            sel = var_pm.get()
            cfg = screen.app.get_cfg()
            cfg['piper_model'] = display_to_file.get(sel, '')
            screen.app.save_cfg()
            au = getattr(screen.app, 'get_audio', lambda: None)()
            if au:
                try:
                    au.update_config(cfg)
                except Exception:
                    pass
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

    # Autocaptura de alimentos
    row_ac = tk.Frame(inner, bg=COL_CARD)
    row_ac.pack(fill='x', pady=6)
    tk.Label(row_ac, text="Autocaptura:", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 14)).pack(side='left')
    var_ac = tk.BooleanVar(value=bool(screen.app.get_cfg().get('auto_capture_enabled', True)))

    def on_toggle_ac():
        try:
            cfg = screen.app.get_cfg(); cfg['auto_capture_enabled'] = bool(var_ac.get()); screen.app.save_cfg()
            screen.toast.show("Autocaptura: " + ("ON" if cfg['auto_capture_enabled'] else "OFF"), 900)
        except Exception:
            pass

    ttk.Checkbutton(row_ac, text="Activada", variable=var_ac, command=on_toggle_ac).pack(side='left', padx=8)
    tk.Label(row_ac, text="Umbral g:", bg=COL_CARD, fg=COL_TEXT).pack(side='left', padx=(12,4))
    var_ac_delta = tk.IntVar(value=int(screen.app.get_cfg().get('auto_capture_min_delta_g', 8)))
    sp_ac = tk.Spinbox(row_ac, from_=1, to=500, textvariable=var_ac_delta, width=5)
    sp_ac.pack(side='left')
    bind_numeric_entry(sp_ac)

    def on_ac_delta(_e=None):
        try:
            cfg = screen.app.get_cfg(); cfg['auto_capture_min_delta_g'] = int(var_ac_delta.get()); screen.app.save_cfg()
            screen.toast.show(f"Umbral: {cfg['auto_capture_min_delta_g']}g", 900)
        except Exception:
            pass

    sp_ac.bind('<FocusOut>', on_ac_delta)
    sp_ac.bind('<Return>', on_ac_delta)

    # Efecto terminal (Typewriter) global
    row_fx = tk.Frame(inner, bg=COL_CARD)
    row_fx.pack(fill='x', pady=8)
    tk.Label(row_fx, text="Efecto terminal (Typewriter):", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 14)).pack(side='left')
    var_fx = tk.BooleanVar(value=bool(screen.app.get_cfg().get('textfx_enabled', True)))

    def on_toggle_fx():
        try:
            cfg = screen.app.get_cfg(); cfg['textfx_enabled'] = bool(var_fx.get()); screen.app.save_cfg()
            screen.toast.show("Typewriter: " + ("ON" if cfg['textfx_enabled'] else "OFF"), 900)
        except Exception:
            pass

    ttk.Checkbutton(row_fx, text="Activado", variable=var_fx, command=on_toggle_fx).pack(side='left', padx=8)

    # Visión (IA): autosugerencias y umbral
    row_vis = tk.Frame(inner, bg=COL_CARD)
    row_vis.pack(fill='x', pady=10)
    tk.Label(row_vis, text="Visión (IA):", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 14)).pack(side='left')

    var_vis = tk.BooleanVar(value=bool(screen.app.get_cfg().get('vision_autosuggest_enabled', False)))
    def on_toggle_vis():
        try:
            cfg = screen.app.get_cfg(); cfg['vision_autosuggest_enabled'] = bool(var_vis.get()); screen.app.save_cfg()
            screen.toast.show("Sugerencias por visión: " + ("ON" if cfg['vision_autosuggest_enabled'] else "OFF"), 900)
        except Exception:
            pass
    ttk.Checkbutton(row_vis, text="Sugerencias proactivas", variable=var_vis, command=on_toggle_vis).pack(side='left', padx=8)

    # Umbral de confianza
    row_thr = tk.Frame(inner, bg=COL_CARD)
    row_thr.pack(fill='x', pady=6)
    tk.Label(row_thr, text="Confianza mínima (0.50-0.95):", bg=COL_CARD, fg=COL_TEXT).pack(side='left')
    var_thr = tk.StringVar(value=str(screen.app.get_cfg().get('vision_confidence_threshold', 0.85)))
    ent_thr = tk.Entry(row_thr, textvariable=var_thr, bg=COL_CARD_HOVER, fg=COL_TEXT, relief='flat', insertbackground=COL_TEXT, width=6)
    ent_thr.pack(side='left', padx=8)

    def on_save_thr():
        try:
            v = float(var_thr.get())
            v = max(0.5, min(0.95, v))
            cfg = screen.app.get_cfg(); cfg['vision_confidence_threshold'] = v; screen.app.save_cfg()
            screen.toast.show(f"Confianza mínima: {v:.2f}", 900)
        except Exception:
            pass
    tk.Button(row_thr, text='Guardar', command=on_save_thr, bg=COL_ACCENT, fg='white', bd=0, relief='flat', cursor='hand2').pack(side='left')

    # Peso mínimo para sugerir
    row_minw = tk.Frame(inner, bg=COL_CARD)
    row_minw.pack(fill='x', pady=6)
    tk.Label(row_minw, text="Peso mínimo (g):", bg=COL_CARD, fg=COL_TEXT).pack(side='left')
    var_minw = tk.StringVar(value=str(screen.app.get_cfg().get('vision_min_weight_g', 20)))
    ent_minw = tk.Entry(row_minw, textvariable=var_minw, bg=COL_CARD_HOVER, fg=COL_TEXT, relief='flat', insertbackground=COL_TEXT, width=8)
    ent_minw.pack(side='left', padx=8)

    def on_save_minw():
        try:
            v = max(0, int(float(var_minw.get())))
            cfg = screen.app.get_cfg(); cfg['vision_min_weight_g'] = v; screen.app.save_cfg()
            screen.toast.show(f"Peso mínimo: {v} g", 900)
        except Exception:
            pass
    tk.Button(row_minw, text='Guardar', command=on_save_minw, bg=COL_ACCENT, fg='white', bd=0, relief='flat', cursor='hand2').pack(side='left')

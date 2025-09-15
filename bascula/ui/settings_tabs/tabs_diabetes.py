# -*- coding: utf-8 -*-
from __future__ import annotations

import tkinter as tk

from bascula.ui.widgets import COL_CARD, COL_TEXT, COL_ACCENT, bind_numeric_entry


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

    # Envío a Nightscout por defecto
    nsdef = tk.Frame(inner, bg=COL_CARD); nsdef.pack(fill='x', pady=(0,8))
    tk.Label(nsdef, text='Enviar a Nightscout por defecto:', bg=COL_CARD, fg=COL_TEXT).pack(side='left')
    var_send_def = tk.BooleanVar(value=bool(screen.app.get_cfg().get('send_to_ns_default', False)))
    def on_send_def():
        try:
            cfg = screen.app.get_cfg(); cfg['send_to_ns_default'] = bool(var_send_def.get()); screen.app.save_cfg()
        except Exception:
            pass
    tk.Checkbutton(nsdef, text='Activado', variable=var_send_def, command=on_send_def, bg=COL_CARD, fg=COL_TEXT, selectcolor=COL_CARD).pack(side='left', padx=8)

    # Umbrales simples e intervalo de lectura
    simple = tk.Frame(inner, bg=COL_CARD); simple.pack(anchor='w', pady=6)
    tk.Label(simple, text='BG baja (mg/dL)', bg=COL_CARD, fg=COL_TEXT).grid(row=0, column=0, sticky='w')
    var_bg_low = tk.StringVar(value=str(screen.app.get_cfg().get('bg_low_mgdl', 70)))
    ent_low = tk.Entry(simple, textvariable=var_bg_low, width=6)
    ent_low.grid(row=1, column=0, sticky='w')
    tk.Label(simple, text='BG alta (mg/dL)', bg=COL_CARD, fg=COL_TEXT).grid(row=0, column=1, sticky='w', padx=(10,0))
    var_bg_high = tk.StringVar(value=str(screen.app.get_cfg().get('bg_high_mgdl', 180)))
    ent_high = tk.Entry(simple, textvariable=var_bg_high, width=6)
    ent_high.grid(row=1, column=1, sticky='w', padx=(10,0))
    tk.Label(simple, text='Intervalo (s)', bg=COL_CARD, fg=COL_TEXT).grid(row=0, column=2, sticky='w', padx=(10,0))
    var_poll = tk.StringVar(value=str(screen.app.get_cfg().get('bg_poll_s', 60)))
    ent_poll = tk.Entry(simple, textvariable=var_poll, width=6)
    ent_poll.grid(row=1, column=2, sticky='w', padx=(10,0))
    try:
        bind_numeric_entry(ent_low, decimals=0)
        bind_numeric_entry(ent_high, decimals=0)
        bind_numeric_entry(ent_poll, decimals=0)
    except Exception:
        pass

    # Parámetros de bolo
    params = [
        ("Objetivo (mg/dL)", 'target_bg_mgdl', 110),
        ("ISF (mg/dL/U)", 'isf_mgdl_per_u', 50),
        ("Ratio HC (g/U)", 'carb_ratio_g_per_u', 10),
        ("DIA (horas)", 'dia_hours', 4),
    ]
    grid = tk.Frame(inner, bg=COL_CARD); grid.pack(anchor='w', pady=(8,4))
    vars_map = {}
    for i,(label,key,default) in enumerate(params):
        row = tk.Frame(grid, bg=COL_CARD); row.grid(row=i//2, column=i%2, padx=8, pady=4, sticky='w')
        tk.Label(row, text=label, bg=COL_CARD, fg=COL_TEXT).pack(anchor='w')
        v = tk.StringVar(value=str(screen.app.get_cfg().get(key, default)))
        e = tk.Entry(row, textvariable=v, width=10)
        e.pack(anchor='w', pady=2)
        try: bind_numeric_entry(e, decimals=1 if 'ratio' in key or 'dia' in key else 0)
        except Exception: pass
        vars_map[key] = v

    # BG thresholds y alertas
    thr_row = tk.Frame(inner, bg=COL_CARD); thr_row.pack(fill='x', pady=6)
    tk.Label(thr_row, text='Umbrales BG (mg/dL):', bg=COL_CARD, fg=COL_TEXT).pack(side='left')
    thr_vars = {}
    for label, key, default in [("Baja <", 'bg_low_threshold', 70), ("Advertencia >", 'bg_warn_threshold', 180), ("Alta >", 'bg_high_threshold', 250)]:
        col = tk.Frame(thr_row, bg=COL_CARD); col.pack(side='left', padx=8)
        tk.Label(col, text=label, bg=COL_CARD, fg=COL_TEXT).pack(anchor='w')
        v = tk.StringVar(value=str(screen.app.get_cfg().get(key, default)))
        e = tk.Entry(col, textvariable=v, width=6)
        e.pack(anchor='w')
        try: bind_numeric_entry(e, decimals=0)
        except Exception: pass
        thr_vars[key] = v

    alerts_row = tk.Frame(inner, bg=COL_CARD); alerts_row.pack(fill='x', pady=6)
    var_alerts = tk.BooleanVar(value=bool(screen.app.get_cfg().get('bg_alerts_enabled', True)))
    var_announce = tk.BooleanVar(value=bool(screen.app.get_cfg().get('bg_announce_on_alert', True)))
    var_every = tk.BooleanVar(value=bool(screen.app.get_cfg().get('bg_announce_every', False)))
    tk.Checkbutton(alerts_row, text='Alertas sonoras en baja/alta', variable=var_alerts, bg=COL_CARD, fg=COL_TEXT, selectcolor=COL_CARD).pack(side='left')
    tk.Checkbutton(alerts_row, text='Anunciar valor en alerta', variable=var_announce, bg=COL_CARD, fg=COL_TEXT, selectcolor=COL_CARD).pack(side='left', padx=8)
    tk.Checkbutton(alerts_row, text='Anunciar cada lectura', variable=var_every, bg=COL_CARD, fg=COL_TEXT, selectcolor=COL_CARD).pack(side='left', padx=8)

    # No molestar (DND) y Snooze
    dnd_row = tk.Frame(inner, bg=COL_CARD); dnd_row.pack(fill='x', pady=6)
    tk.Label(dnd_row, text='No molestar (DND):', bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 14)).pack(side='left')
    var_dnd = tk.BooleanVar(value=bool(screen.app.get_cfg().get('bg_dnd_enabled', False)))
    tk.Checkbutton(dnd_row, text='Activado', variable=var_dnd, bg=COL_CARD, fg=COL_TEXT, selectcolor=COL_CARD).pack(side='left', padx=8)

    time_row = tk.Frame(inner, bg=COL_CARD); time_row.pack(fill='x', pady=6)
    tk.Label(time_row, text='Desde (HH:MM):', bg=COL_CARD, fg=COL_TEXT).pack(side='left')
    var_dnd_start = tk.StringVar(value=str(screen.app.get_cfg().get('bg_dnd_start', '22:00')))
    tk.Entry(time_row, textvariable=var_dnd_start, width=8).pack(side='left', padx=6)
    tk.Label(time_row, text='Hasta (HH:MM):', bg=COL_CARD, fg=COL_TEXT).pack(side='left', padx=(10,2))
    var_dnd_end = tk.StringVar(value=str(screen.app.get_cfg().get('bg_dnd_end', '07:00')))
    tk.Entry(time_row, textvariable=var_dnd_end, width=8).pack(side='left', padx=6)

    var_dnd_allow_low = tk.BooleanVar(value=bool(screen.app.get_cfg().get('bg_dnd_allow_low_override', True)))
    tk.Checkbutton(inner, text='Permitir alertas en BAJA durante DND', variable=var_dnd_allow_low, bg=COL_CARD, fg=COL_TEXT, selectcolor=COL_CARD).pack(anchor='w', pady=(2,6))

    snooze_row = tk.Frame(inner, bg=COL_CARD); snooze_row.pack(fill='x', pady=6)
    tk.Label(snooze_row, text='Snooze por defecto (min):', bg=COL_CARD, fg=COL_TEXT).pack(side='left')
    var_snooze = tk.StringVar(value=str(screen.app.get_cfg().get('bg_snooze_minutes', 15)))
    tk.Entry(snooze_row, textvariable=var_snooze, width=6).pack(side='left', padx=6)

    def on_save_all():
        try:
            cfg = screen.app.get_cfg()
            def to_int(v, d):
                try: return int(float(v))
                except Exception: return d
            cfg['bg_low_mgdl'] = to_int(var_bg_low.get(), 70)
            cfg['bg_high_mgdl'] = to_int(var_bg_high.get(), 180)
            cfg['bg_poll_s'] = to_int(var_poll.get(), 60)
            cfg['target_bg_mgdl'] = to_int(vars_map['target_bg_mgdl'].get(), 110)
            cfg['isf_mgdl_per_u'] = to_int(vars_map['isf_mgdl_per_u'].get(), 50)
            cfg['carb_ratio_g_per_u'] = to_int(vars_map['carb_ratio_g_per_u'].get(), 10)
            cfg['dia_hours'] = to_int(vars_map['dia_hours'].get(), 4)
            cfg['bg_low_threshold'] = to_int(thr_vars['bg_low_threshold'].get(), 70)
            cfg['bg_warn_threshold'] = max(cfg['bg_low_threshold']+10, to_int(thr_vars['bg_warn_threshold'].get(), 180))
            cfg['bg_high_threshold'] = max(cfg['bg_warn_threshold']+20, to_int(thr_vars['bg_high_threshold'].get(), 250))
            cfg['bg_alerts_enabled'] = bool(var_alerts.get())
            cfg['bg_announce_on_alert'] = bool(var_announce.get())
            cfg['bg_announce_every'] = bool(var_every.get())
            # DND + Snooze
            cfg['bg_dnd_enabled'] = bool(var_dnd.get())
            cfg['bg_dnd_start'] = (var_dnd_start.get() or '22:00').strip()
            cfg['bg_dnd_end'] = (var_dnd_end.get() or '07:00').strip()
            cfg['bg_dnd_allow_low_override'] = bool(var_dnd_allow_low.get())
            try:
                cfg['bg_snooze_minutes'] = max(1, int(float(var_snooze.get())))
            except Exception:
                cfg['bg_snooze_minutes'] = 15
            screen.app.save_cfg()
            screen.toast.show('Parámetros BG guardados', 900)
        except Exception as e:
            screen.toast.show(f'Error: {e}', 1300)

    tk.Button(inner, text='Guardar parámetros', command=on_save_all, bg=COL_ACCENT, fg='white', bd=0, relief='flat', cursor='hand2').pack(pady=10)

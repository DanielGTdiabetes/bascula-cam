# -*- coding: utf-8 -*-
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from bascula.ui.widgets import COL_CARD, COL_TEXT, COL_ACCENT
from bascula.ui.settings_tabs.utils import create_scrollable_tab


def add_tab(screen, notebook):
    inner = create_scrollable_tab(notebook, "Tema")

    # Cargar temas disponibles
    try:
        from bascula.config.themes import THEMES, get_theme_manager, update_color_constants
    except Exception:
        THEMES = {}
        get_theme_manager = lambda: None
        update_color_constants = lambda: None

    names = list(THEMES.keys())
    display = {k: getattr(THEMES[k], 'display_name', k) for k in names}
    current = str(screen.app.get_cfg().get('ui_theme', names[0] if names else 'dark_modern'))

    row = tk.Frame(inner, bg=COL_CARD); row.pack(fill='x', pady=6)
    tk.Label(row, text='Tema de la interfaz:', bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 14)).pack(side='left')
    var = tk.StringVar(value=current if current in names else (names[0] if names else 'dark_modern'))
    cb = ttk.Combobox(row, textvariable=var, state='readonly', values=[display[n] for n in names] if names else [])
    cb.pack(side='left', padx=8)

    def name_from_display(disp: str) -> str:
        for k, v in display.items():
            if v == disp:
                return k
        return var.get()

    # Mantener estado de preview
    preview_after = {'id': None}
    original = {'name': current}

    def restore_original():
        try:
            from bascula.config.themes import get_theme_manager, update_color_constants
            tm = get_theme_manager()
            if tm and tm.set_theme(original['name']):
                tm.apply_to_root(screen.winfo_toplevel())
                update_color_constants()
                cfg = screen.app.get_cfg(); cfg['ui_theme'] = original['name']; screen.app.save_cfg()
                screen.toast.show(f"Restaurado: {display.get(original['name'], original['name'])}", 900)
        except Exception:
            pass

    def on_apply():
        try:
            sel_disp = cb.get()
            theme_name = name_from_display(sel_disp)
            tm = get_theme_manager()
            if tm and tm.set_theme(theme_name):
                tm.apply_to_root(screen.winfo_toplevel())
                update_color_constants()
                cfg = screen.app.get_cfg(); cfg['ui_theme'] = theme_name; screen.app.save_cfg()
                screen.toast.show(f"Tema aplicado: {display.get(theme_name, theme_name)}", 1200)
        except Exception as e:
            screen.toast.show(f"Error: {e}", 1500)

    def on_preview():
        try:
            sel_disp = cb.get()
            theme_name = name_from_display(sel_disp)
            from bascula.config.themes import get_theme_manager, update_color_constants
            tm = get_theme_manager()
            if tm and tm.set_theme(theme_name):
                tm.apply_to_root(screen.winfo_toplevel())
                update_color_constants()
                screen.toast.show(f"Vista previa: {display.get(theme_name, theme_name)}", 1000)
                # Cancelar preview previa
                if preview_after['id']:
                    try: screen.after_cancel(preview_after['id'])
                    except Exception: pass
                preview_after['id'] = screen.after(3000, restore_original)
        except Exception as e:
            screen.toast.show(f"Error preview: {e}", 1500)

    bar = tk.Frame(inner, bg=COL_CARD); bar.pack(fill='x')
    tk.Button(bar, text='Aplicar', command=on_apply, bg=COL_ACCENT, fg='white', bd=0, relief='flat', cursor='hand2').pack(side='left', pady=6, padx=(0,6))
    tk.Button(bar, text='Vista previa', command=on_preview, bg='#2a3142', fg='white', bd=0, relief='flat', cursor='hand2').pack(side='left', pady=6)
    tk.Button(bar, text='Restaurar', command=restore_original, bg='#6b7280', fg='white', bd=0, relief='flat', cursor='hand2').pack(side='left', pady=6, padx=6)

    # Efectos
    eff = tk.Frame(inner, bg=COL_CARD); eff.pack(fill='x', pady=6)
    tk.Label(eff, text='Efectos visuales:', bg=COL_CARD, fg=COL_TEXT).pack(side='left')
    var_scan = tk.BooleanVar(value=bool(screen.app.get_cfg().get('theme_scanlines', False)))
    var_glow = tk.BooleanVar(value=bool(screen.app.get_cfg().get('theme_glow', False)))

    def on_toggle_scan():
        try:
            cfg = screen.app.get_cfg(); cfg['theme_scanlines'] = bool(var_scan.get()); screen.app.save_cfg()
            tm = get_theme_manager()
            if tm:
                if cfg['theme_scanlines']:
                    tm._apply_scanlines(screen.winfo_toplevel())
                else:
                    tm._remove_scanlines()
            screen.toast.show(f"Scanlines: {'ON' if cfg['theme_scanlines'] else 'OFF'}", 900)
        except Exception:
            pass

    tk.Checkbutton(eff, text='Scanlines CRT', variable=var_scan, command=on_toggle_scan, bg=COL_CARD, fg=COL_TEXT, selectcolor=COL_CARD).pack(side='left', padx=8)
    def on_toggle_glow():
        try:
            cfg = screen.app.get_cfg(); cfg['theme_glow'] = bool(var_glow.get()); screen.app.save_cfg()
            screen.toast.show(f"Glow: {'ON' if cfg['theme_glow'] else 'OFF'}", 900)
        except Exception:
            pass
    tk.Checkbutton(eff, text='Efecto Glow', variable=var_glow, command=on_toggle_glow, bg=COL_CARD, fg=COL_TEXT, selectcolor=COL_CARD).pack(side='left', padx=8)

    # Info de estado
    cur_label = tk.Label(inner, text=f"Tema actual: {display.get(var.get(), var.get())}", bg=COL_CARD, fg=COL_TEXT)
    cur_label.pack(anchor='w', pady=(6,0))
    def update_cur(_e=None):
        cur_label.config(text=f"Tema actual: {display.get(name_from_display(cb.get()), cb.get())}")
    cb.bind('<<ComboboxSelected>>', update_cur)

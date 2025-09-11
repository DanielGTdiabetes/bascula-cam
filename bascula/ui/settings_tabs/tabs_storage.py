# -*- coding: utf-8 -*-
from __future__ import annotations

import tkinter as tk
from pathlib import Path

from bascula.ui.widgets import COL_CARD, COL_TEXT, COL_ACCENT, COL_DANGER

try:
    from bascula.services.retention import prune_jsonl
except Exception:
    prune_jsonl = None


def add_tab(screen, notebook):
    tab = tk.Frame(notebook, bg=COL_CARD)
    notebook.add(tab, text="Datos")

    inner = tk.Frame(tab, bg=COL_CARD)
    inner.pack(fill="both", expand=True, padx=16, pady=12)

    # Mantener fotos
    fr = tk.Frame(inner, bg=COL_CARD)
    fr.pack(fill='x', pady=6)
    tk.Label(fr, text="Mantener fotos temporales entre reinicios:", bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 14)).pack(side='left')
    var_keep = tk.BooleanVar(value=bool(screen.app.get_cfg().get('keep_photos', False)))

    def on_toggle_photos():
        try:
            cfg = screen.app.get_cfg(); cfg['keep_photos'] = bool(var_keep.get()); screen.app.save_cfg()
            screen.toast.show("Fotos: " + ("mantener" if cfg['keep_photos'] else "no guardar"), 900)
        except Exception:
            pass

    tk.Checkbutton(fr, text="Activado", variable=var_keep, command=on_toggle_photos, bg=COL_CARD, fg=COL_TEXT, selectcolor=COL_CARD).pack(side='left', padx=8)

    # Limpiar histórico
    def on_clear_history():
        try:
            path = Path.home() / '.config' / 'bascula' / 'meals.jsonl'
            if not path.exists():
                screen.toast.show("Sin histórico", 900)
                return
            if prune_jsonl is None:
                path.write_text('', encoding='utf-8')
                screen.toast.show("Histórico limpiado (simple)", 900)
                return
            cfg = screen.app.get_cfg()
            prune_jsonl(
                path,
                max_days=int(cfg.get('meals_max_days', 0) or 0),
                max_entries=int(cfg.get('meals_max_entries', 0) or 0),
                max_bytes=int(cfg.get('meals_max_bytes', 0) or 0),
            )
            screen.toast.show("Histórico limpiado", 1000)
        except Exception as e:
            screen.toast.show(f"Error: {e}", 1300, COL_DANGER)

    tk.Button(inner, text="Limpiar histórico", command=on_clear_history, bg=COL_ACCENT, fg='white', bd=0, relief='flat', cursor='hand2').pack(pady=12)


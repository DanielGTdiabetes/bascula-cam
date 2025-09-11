# -*- coding: utf-8 -*-
from __future__ import annotations

import tkinter as tk
from pathlib import Path

from bascula.ui.widgets import COL_CARD, COL_TEXT, COL_ACCENT, COL_DANGER, TouchScrollableFrame

try:
    from bascula.services.retention import prune_jsonl
except Exception:
    prune_jsonl = None


def add_tab(screen, notebook):
    tab = tk.Frame(notebook, bg=COL_CARD)
    notebook.add(tab, text="Datos")

    sf = TouchScrollableFrame(tab, bg=COL_CARD)
    sf.pack(fill="both", expand=True, padx=16, pady=12)
    inner = sf.inner

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

    # Retención básica (días, entradas, MB)
    ret = tk.Frame(inner, bg=COL_CARD); ret.pack(fill='x', pady=6)
    tk.Label(ret, text='Retención de histórico:', bg=COL_CARD, fg=COL_TEXT).pack(anchor='w')
    row = tk.Frame(ret, bg=COL_CARD); row.pack(anchor='w', pady=(4,0))
    vars_ret = {}
    for label, key, default, width in [
        ('Días máx', 'meals_max_days', 180, 6),
        ('Entradas máx', 'meals_max_entries', 2000, 8),
        ('Tamaño máx (MB)', 'meals_max_bytes', 50, 10),
    ]:
        col = tk.Frame(row, bg=COL_CARD); col.pack(side='left', padx=8)
        tk.Label(col, text=label, bg=COL_CARD, fg=COL_TEXT).pack(anchor='w')
        v = tk.StringVar(value=str(int((screen.app.get_cfg().get(key, default*1_000_000 if 'bytes' in key else default)) / (1_000_000 if 'bytes' in key else 1))))
        e = tk.Entry(col, textvariable=v, width=width); e.pack(anchor='w')
        vars_ret[key] = v

    def on_save_ret():
        try:
            cfg = screen.app.get_cfg()
            cfg['meals_max_days'] = int(vars_ret['meals_max_days'].get())
            cfg['meals_max_entries'] = int(vars_ret['meals_max_entries'].get())
            cfg['meals_max_bytes'] = max(0, int(vars_ret['meals_max_bytes'].get())) * 1_000_000
            screen.app.save_cfg()
            screen.toast.show('Retención aplicada', 900)
        except Exception as e:
            screen.toast.show(f'Error: {e}', 1300, COL_DANGER)

    tk.Button(inner, text='Guardar retención', command=on_save_ret, bg=COL_ACCENT, fg='white', bd=0, relief='flat', cursor='hand2').pack(pady=6, anchor='w')

    # Estadísticas básicas de ficheros
    stats = tk.Frame(inner, bg=COL_CARD); stats.pack(fill='x', pady=6)
    lbl = tk.Label(stats, text='Recetas/Queue/Fotos: (pulsa Refrescar)', bg=COL_CARD, fg=COL_TEXT)
    lbl.pack(anchor='w')

    def refresh_stats():
        try:
            base = Path.home() / '.config' / 'bascula'
            photos_dir = Path.home() / '.bascula' / 'photos' / 'staging'
            def count_size(p: Path):
                if not p.exists():
                    return 0, 0
                try:
                    with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                        cnt = sum(1 for _ in f)
                except Exception:
                    cnt = 0
                try:
                    size = p.stat().st_size
                except Exception:
                    size = 0
                return cnt, size
            rc, rs = count_size(base / 'recipes.jsonl')
            oc, osz = count_size(base / 'offqueue.jsonl')
            pc = 0; psz = 0
            if photos_dir.exists():
                for p in photos_dir.glob('*.jpg'):
                    try:
                        psz += p.stat().st_size; pc += 1
                    except Exception:
                        pass
            fmt = lambda b: f"{(b/1_000_000):.2f} MB"
            lbl.config(text=f"Recetas: {rc} ({fmt(rs)}), OFFQ: {oc} ({fmt(osz)}), Fotos: {pc} ({fmt(psz)})")
        except Exception:
            pass

    tk.Button(inner, text='Refrescar', command=refresh_stats, bg=COL_ACCENT, fg='white', bd=0, relief='flat', cursor='hand2').pack(pady=6, anchor='w')

    # Limpiar fotos (staging)
    def clear_photos():
        try:
            st = Path.home() / '.bascula' / 'photos' / 'staging'
            n = 0
            if st.exists():
                for p in st.glob('*.jpg'):
                    try:
                        p.unlink(); n += 1
                    except Exception:
                        pass
            screen.toast.show(f'Fotos eliminadas: {n}', 900)
        except Exception:
            pass

    tk.Button(inner, text='Limpiar fotos (staging)', command=clear_photos, bg=COL_DANGER, fg='white', bd=0, relief='flat', cursor='hand2').pack(pady=6, anchor='w')

    # Limpieza segura inmediata de recipes/offqueue
    def clean_now():
        try:
            base = Path.home() / '.config' / 'bascula'
            if prune_jsonl:
                prune_jsonl(base / 'recipes.jsonl', max_days=365, max_entries=1000, max_bytes=20*1024*1024)
                prune_jsonl(base / 'offqueue.jsonl', max_days=365, max_entries=10000, max_bytes=50*1024*1024)
            screen.toast.show('Limpieza realizada', 900)
            refresh_stats()
        except Exception as e:
            screen.toast.show(f'Error limpiando: {e}', 1300, COL_DANGER)

    tk.Button(inner, text='Limpiar ahora (recipes/offq)', command=clean_now, bg=COL_ACCENT, fg='white', bd=0, relief='flat', cursor='hand2').pack(pady=6, anchor='w')

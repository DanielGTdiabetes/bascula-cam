# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tkinter as tk

from bascula.ui.widgets import COL_CARD, COL_TEXT


def _repo_root(start: Path) -> Path:
    cur = start
    for p in [cur] + list(cur.parents):
        if (p / '.git').exists():
            return p
    return start


def add_tab(screen, notebook):
    tab = tk.Frame(notebook, bg=COL_CARD)
    notebook.add(tab, text="OTA")

    inner = tk.Frame(tab, bg=COL_CARD)
    inner.pack(fill="both", expand=True, padx=16, pady=16)

    status = tk.StringVar(value="Listo")

    def set_status(msg: str):
        status.set(msg)

    tk.Label(inner, textvariable=status, bg=COL_CARD, fg=COL_TEXT, font=("DejaVu Sans", 12)).pack(anchor='w')

    def on_check():
        try:
            root = _repo_root(Path(__file__).resolve())
            subprocess.run(["git", "fetch", "--all", "--tags"], cwd=str(root), check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            local = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(root), text=True).strip()
            # Detect upstream
            remotes = subprocess.check_output(["git", "remote"], cwd=str(root), text=True).strip().splitlines()
            remote = "origin" if "origin" in remotes else (remotes[0] if remotes else "origin")
            # try HEAD branch
            remote_branch = None
            try:
                show = subprocess.check_output(["git", "remote", "show", remote], cwd=str(root), text=True)
                for line in show.splitlines():
                    if "HEAD branch:" in line:
                        remote_branch = line.split(":", 1)[-1].strip()
                        break
            except Exception:
                pass
            upstream = f"{remote}/{remote_branch or 'main'}"
            remote_rev = subprocess.check_output(["git", "rev-parse", upstream], cwd=str(root), text=True).strip()
            if local == remote_rev:
                set_status(f"Sin novedades ({local[:7]})")
            else:
                set_status(f"Actualización disponible: {remote_rev[:7]} (local {local[:7]})")
        except Exception as e:
            set_status(f"Error al comprobar: {e}")

    btns = tk.Frame(inner, bg=COL_CARD)
    btns.pack(pady=8)
    tk.Button(btns, text="Comprobar actualización", command=on_check, bg="#3b82f6", fg='white', bd=0, relief='flat', cursor='hand2').pack(side='left', padx=6)
    # Por seguridad, dejamos la acción de actualizar para una futura versión
    tk.Button(btns, text="Actualizar (deshabilitado)", state='disabled', bg="#6b7280", fg='white', bd=0, relief='flat').pack(side='left', padx=6)


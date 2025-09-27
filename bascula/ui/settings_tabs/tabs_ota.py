# -*- coding: utf-8 -*-
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tkinter as tk

from bascula.ui.widgets import COL_CARD, COL_TEXT, COL_ACCENT
from bascula.ui.settings_tabs.utils import create_scrollable_tab


def _repo_root(start: Path) -> Path:
    cur = start
    for p in [cur] + list(cur.parents):
        if (p / '.git').exists():
            return p
    return start


def add_tab(screen, notebook):
    inner = create_scrollable_tab(notebook, "OTA", padding=(16, 16))

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
    # Actualizar (con seguridad básica)
    auto_restart = tk.BooleanVar(value=True)
    tk.Checkbutton(inner, text='Reiniciar mini‑web tras actualizar', variable=auto_restart, bg=COL_CARD, fg=COL_TEXT, selectcolor=COL_CARD).pack(anchor='w')

    def on_update():
        import threading
        def worker():
            try:
                root = _repo_root(Path(__file__).resolve())
                # Evitar sobrescribir cambios locales
                rc = subprocess.run(["git", "diff", "--quiet"], cwd=str(root)).returncode
                if rc != 0:
                    set_status('Hay cambios locales; git limpio requerido.')
                    return
                # Remember current rev
                old_rev = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(root), text=True).strip()
                # Detect upstream
                remotes = subprocess.check_output(["git", "remote"], cwd=str(root), text=True).strip().splitlines()
                remote = "origin" if "origin" in remotes else (remotes[0] if remotes else "origin")
                head_branch = None
                try:
                    show = subprocess.check_output(["git", "remote", "show", remote], cwd=str(root), text=True)
                    for line in show.splitlines():
                        if 'HEAD branch:' in line:
                            head_branch = line.split(':',1)[-1].strip()
                            break
                except Exception:
                    pass
                upstream = f"{remote}/{head_branch or 'main'}"
                subprocess.run(["git", "fetch", "--all", "--tags"], cwd=str(root), check=True)
                new_rev = subprocess.check_output(["git", "rev-parse", upstream], cwd=str(root), text=True).strip()
                if old_rev == new_rev:
                    set_status('Ya estás en la última versión.')
                    return
                subprocess.run(["git", "reset", "--hard", new_rev], cwd=str(root), check=True)
                req = root / 'requirements.txt'
                if req.exists():
                    subprocess.run(["python3", "-m", "pip", "install", "--upgrade", "-r", str(req)], cwd=str(root), check=False)
                # Prueba import mínima
                code = "import importlib; import sys; m=importlib.import_module('bascula.ui.app'); print('OK')"
                p = subprocess.run(["python3", "-c", code], cwd=str(root), capture_output=True, text=True)
                if p.returncode != 0:
                    raise RuntimeError(p.stderr.strip() or p.stdout.strip())
                set_status('Actualizado correctamente.')
                if auto_restart.get():
                    restart_web()
            except Exception as e:
                set_status(f"Error al actualizar: {e}")
        threading.Thread(target=worker, daemon=True).start()

    tk.Button(btns, text="Actualizar", command=on_update, bg="#6b7280", fg='white', bd=0, relief='flat', cursor='hand2').pack(side='left', padx=6)

    # Reinicio mini‑web opcional
    def restart_web():
        try:
            p = subprocess.run(["systemctl", "restart", "bascula-web.service"], capture_output=True, text=True, timeout=8)
            ok = (p.returncode == 0)
            set_status("Mini‑web reiniciada" if ok else f"Fallo al reiniciar mini‑web: {p.stderr.strip() or p.stdout.strip()}")
        except Exception as e:
            set_status(f"Error reiniciando mini‑web: {e}")

    tk.Button(inner, text='Reiniciar mini‑web', command=restart_web, bg=COL_ACCENT, fg='white', bd=0, relief='flat', cursor='hand2').pack(pady=6, anchor='w')

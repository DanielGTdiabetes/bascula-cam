#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pantalla de recuperación minimalista.

Se muestra cuando la actualización falla o la UI principal no puede
iniciarse. Usa la paleta de `bascula.ui.widgets` para mantener un estilo
consistente. Permite intentar una actualización y reiniciar el sistema.
"""
from __future__ import annotations

import subprocess
import threading
from pathlib import Path
import tkinter as tk
from bascula.ui.widgets import COL_BG, COL_CARD, COL_TEXT, COL_ACCENT, FS_TITLE, FS_TEXT


def _repo_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if (p / ".git").exists():
            return p
    return start


def main():
    root = tk.Tk()
    root.configure(bg=COL_BG)
    try:
        root.attributes("-fullscreen", True)
    except Exception:
        pass

    container = tk.Frame(root, bg=COL_CARD)
    container.pack(expand=True, fill="both", padx=40, pady=40)

    title = tk.Label(
        container,
        text="Modo recuperación",
        bg=COL_CARD,
        fg=COL_ACCENT,
        font=("DejaVu Sans Mono", max(18, FS_TITLE), "bold"),
    )
    title.pack(pady=(20, 10))

    msg = tk.Label(
        container,
        text=(
            "La actualización falló o la UI no pudo iniciarse.\n"
            "Reinicia la báscula o contacta con soporte."
        ),
        bg=COL_CARD,
        fg=COL_TEXT,
        font=("DejaVu Sans Mono", max(12, FS_TEXT)),
        justify="center",
    )
    msg.pack(pady=10)

    status = tk.StringVar()
    tk.Label(
        container,
        textvariable=status,
        bg=COL_CARD,
        fg=COL_TEXT,
        font=("DejaVu Sans Mono", max(11, FS_TEXT)),
        justify="center",
    ).pack(pady=(0, 10))

    def on_update():
        def worker():
            try:
                status.set("Actualizando…")
                root_path = _repo_root(Path(__file__).resolve())
                subprocess.run(["git", "fetch", "--all", "--tags"], cwd=root_path, check=True)
                subprocess.run(["git", "reset", "--hard", "origin/main"], cwd=root_path, check=True)
                req = root_path / "requirements.txt"
                if req.exists():
                    subprocess.run([
                        "python3",
                        "-m",
                        "pip",
                        "install",
                        "--upgrade",
                        "-r",
                        str(req),
                    ], cwd=root_path, check=False)
                status.set("Actualización completada. Reinicia para aplicar.")
            except Exception as e:
                status.set(f"Error al actualizar: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def on_reboot():
        status.set("Reiniciando…")
        try:
            subprocess.Popen(["sudo", "reboot"])
        except Exception as e:
            status.set(f"Error al reiniciar: {e}")

    btns = tk.Frame(container, bg=COL_CARD)
    btns.pack(pady=(30, 10))

    tk.Button(
        btns,
        text="Actualizar",
        command=on_update,
        bg=COL_ACCENT,
        fg=COL_TEXT,
        bd=0,
        relief="flat",
    ).pack(side="left", padx=5)

    tk.Button(
        btns,
        text="Reiniciar",
        command=on_reboot,
        bg=COL_ACCENT,
        fg=COL_TEXT,
        bd=0,
        relief="flat",
    ).pack(side="left", padx=5)

    tk.Button(
        btns,
        text="Cerrar",
        command=root.destroy,
        bg=COL_ACCENT,
        fg=COL_TEXT,
        bd=0,
        relief="flat",
    ).pack(side="left", padx=5)

    root.mainloop()


if __name__ == "__main__":
    main()

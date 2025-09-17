#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pantalla de recuperación minimalista.

Se muestra cuando la actualización falla o la UI principal no puede
iniciarse. Usa la paleta de `bascula.ui.widgets` para mantener un estilo
consistente. Permite intentar una actualización y reiniciar el sistema.
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path
import tkinter as tk

from bascula.services.ota import OTAService
from bascula.ui.widgets import COL_BG, COL_CARD, COL_TEXT, COL_ACCENT, FS_TITLE, FS_TEXT


def _repo_root(start: Path) -> Path:
    for candidate in [start, *start.parents]:
        if (candidate / ".git").exists():
            return candidate
    return start


class RecoveryUI:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.configure(bg=COL_BG)
        try:
            self.root.attributes("-fullscreen", True)
        except Exception:
            self.root.geometry("960x600")

        container = tk.Frame(self.root, bg=COL_CARD)
        container.pack(expand=True, fill="both", padx=40, pady=40)

        tk.Label(
            container,
            text="Modo recuperación",
            bg=COL_CARD,
            fg=COL_ACCENT,
            font=("DejaVu Sans", max(FS_TITLE, 24), "bold"),
        ).pack(pady=(12, 6))

        tk.Label(
            container,
            text=(
                "La interfaz principal no se pudo iniciar.\n"
                "Puedes intentar una actualización OTA o reintentar el arranque."
            ),
            bg=COL_CARD,
            fg=COL_TEXT,
            font=("DejaVu Sans", max(FS_TEXT, 14)),
            justify="center",
        ).pack(pady=(0, 12))

        self.status = tk.StringVar(value="Listo")
        tk.Label(
            container,
            textvariable=self.status,
            bg=COL_CARD,
            fg=COL_TEXT,
            font=("DejaVu Sans", max(FS_TEXT - 2, 12)),
            justify="center",
        ).pack(pady=(0, 16))

        buttons = tk.Frame(container, bg=COL_CARD)
        buttons.pack(pady=20)

        tk.Button(
            buttons,
            text="Reintentar UI",
            command=self._retry,
            bg=COL_ACCENT,
            fg="white",
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=18,
            pady=12,
        ).pack(side="left", padx=8)

        tk.Button(
            buttons,
            text="Actualizar OTA",
            command=self._run_ota,
            bg="#2563eb",
            fg="white",
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=18,
            pady=12,
        ).pack(side="left", padx=8)

        tk.Button(
            buttons,
            text="Salir",
            command=self.root.destroy,
            bg="#6b7280",
            fg="white",
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=18,
            pady=12,
        ).pack(side="left", padx=8)

        repo = _repo_root(Path(__file__).resolve())
        self.ota = OTAService(repo_path=repo)

    # ------------------------------------------------------------------ actions
    def _retry(self) -> None:
        self.status.set("Relanzando interfaz…")
        try:
            self.root.destroy()
            os.execl(sys.executable, sys.executable, "main.py")
        except Exception as exc:
            self.status.set(f"Error al relanzar: {exc}")

    def _run_ota(self) -> None:
        if self.ota.is_running():
            self.status.set("Actualización ya en curso…")
            return

        self.status.set("Descargando actualización…")

        def _callback(result: dict) -> None:
            def update_label() -> None:
                if result.get("success"):
                    ver = result.get("version", "")
                    self.status.set(f"OTA completada ({ver}). Reinicia la báscula.")
                else:
                    self.status.set(f"OTA falló: {result.get('error')}")

            try:
                self.root.after(0, update_label)
            except Exception:
                update_label()

        ok = self.ota.trigger_update(callback=_callback)
        if not ok:
            self.status.set("No se pudo iniciar OTA. Consulta logs.")

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    ui = RecoveryUI()
    ui.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())

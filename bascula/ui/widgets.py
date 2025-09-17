"""Reusable widgets for the simplified kiosk UI."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

class TopBar(ttk.Frame):
    """Navigation header with three fixed buttons."""

    def __init__(self, master: tk.Misc, app: "BasculaApp") -> None:
        super().__init__(master)
        self.app = app
        self.configure(padding=(16, 12), style="TFrame")

        title = ttk.Label(self, text="Báscula Cam", style="TLabel", font=("DejaVu Sans", 20, "bold"))
        title.pack(side=tk.LEFT)

        btn_container = ttk.Frame(self, style="TFrame")
        btn_container.pack(side=tk.RIGHT)

        buttons = [
            ("Home", "home"),
            ("Pesar", "scale"),
            ("Ajustes", "settings"),
        ]
        for text, screen in buttons:
            button = ttk.Button(
                btn_container,
                text=text,
                command=lambda name=screen: self.app.show_screen(name),
            )
            button.pack(side=tk.LEFT, padx=6)

        separator = ttk.Separator(self, orient=tk.HORIZONTAL)
        separator.pack(fill=tk.X, side=tk.BOTTOM, pady=(12, 0))

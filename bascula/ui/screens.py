"""Minimal screen set used by the simplified kiosk application."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from bascula.ui.widgets_mascota import MascotaCanvas


class BaseScreen(ttk.Frame):
    """Base class for simple Tkinter screens."""

    name = "base"
    title = "Pantalla"

    def __init__(self, master: tk.Misc, app: "BasculaApp") -> None:
        super().__init__(master, style="TFrame")
        self.app = app
        self.configure(padding=32)

        self.heading = ttk.Label(self, text=self.title, style="TLabel", font=("DejaVu Sans", 28, "bold"))
        self.heading.pack(anchor=tk.W, pady=(0, 24))

    def on_show(self) -> None:  # pragma: no cover - hooks for future extension
        """Called when the screen is shown."""


class HomeScreen(BaseScreen):
    name = "home"
    title = "Inicio"

    def __init__(self, master: tk.Misc, app: "BasculaApp") -> None:
        super().__init__(master, app)
        container = ttk.Frame(self, style="TFrame")
        container.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(container, style="TFrame")
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        welcome = ttk.Label(left, text="Bienvenido", style="TLabel", font=("DejaVu Sans", 18))
        welcome.pack(anchor=tk.W, pady=(0, 12))

        description = ttk.Label(
            left,
            text="Selecciona una opción en la barra superior para comenzar.",
            style="TLabel",
            wraplength=360,
            justify=tk.LEFT,
        )
        description.pack(anchor=tk.W)

        right = ttk.Frame(container, style="TFrame")
        right.pack(side=tk.RIGHT, fill=tk.BOTH)

        mascot = MascotaCanvas(right)
        mascot.pack(padx=12, pady=12)
        self.mascota = mascot


class ScaleScreen(BaseScreen):
    name = "scale"
    title = "Pesar"

    def __init__(self, master: tk.Misc, app: "BasculaApp") -> None:
        super().__init__(master, app)
        message = ttk.Label(
            self,
            text="Coloca el objeto en la báscula y sigue las instrucciones.",
            style="TLabel",
            wraplength=480,
            justify=tk.LEFT,
        )
        message.pack(anchor=tk.W)


class SettingsScreen(BaseScreen):
    name = "settings"
    title = "Ajustes"

    def __init__(self, master: tk.Misc, app: "BasculaApp") -> None:
        super().__init__(master, app)
        info = ttk.Label(
            self,
            text="Configura la aplicación desde esta pantalla.",
            style="TLabel",
            wraplength=480,
            justify=tk.LEFT,
        )
        info.pack(anchor=tk.W)

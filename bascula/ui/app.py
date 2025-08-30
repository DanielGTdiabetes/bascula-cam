# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk

from utils import save_config
from bascula.ui.screens import HomeScreen, SettingsScreen
from serial_reader import SerialReader
from tare_manager import TareManager
from utils import MovingAverage


class BasculaAppTk:
    """
    Orquestador principal de la aplicación Tkinter:
    - Crea servicios (serie, tara, smoothing).
    - Gestiona navegación entre pantallas (Home <-> Ajustes).
    """

    def __init__(self, root: tk.Tk, cfg: dict):
        self.root = root
        self.cfg = cfg

        # Ventana principal
        self.root.title("Báscula Digital Pro")
        self.root.attributes("-fullscreen", True)
        self.root.configure(bg="#0f1115")  # fondo oscuro

        # Tema ttk básico
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        # Servicios de dominio
        self.reader = None
        self.tare = TareManager(calib_factor=self.cfg.get("calib_factor", 1.0), min_display=0.0)
        self.smoother = MovingAverage(size=self.cfg.get("smoothing", 5))

        # Arrancar serie
        try:
            self.reader = SerialReader(port=self.cfg.get("port", "/dev/serial0"),
                                       baud=self.cfg.get("baud", 115200))
            self.reader.start()
        except Exception as e:
            # No rompemos la app si la serie falla; la Home mostrará “—.—”
            print(f"[SERIE] No se pudo abrir {self.cfg.get('port')} @ {self.cfg.get('baud')}: {e}", flush=True)

        # Contenedor de pantallas
        self._container = tk.Frame(self.root, bg="#0f1115")
        self._container.pack(fill="both", expand=True)

        self._screens = {}
        self._current_name = None

        # Crear pantallas
        self._screens["home"] = HomeScreen(
            parent=self._container,
            app=self,
            on_open_settings=lambda: self.navigate("settings")
        )
        self._screens["settings"] = SettingsScreen(
            parent=self._container,
            app=self,
            on_back=lambda: self.navigate("home")
        )

        # Mostrar Home al inicio
        self.navigate("home")

        # Atajos
        self.root.bind("<Escape>", lambda e: self.root.destroy())

    # ---------- API que usan las pantallas ----------

    def get_reader(self):
        return self.reader

    def get_tare(self):
        return self.tare

    def get_smoother(self):
        return self.smoother

    def get_cfg(self):
        return self.cfg

    def save_cfg(self):
        save_config(self.cfg)

    # ---------- Navegación ----------

    def navigate(self, name: str):
        if self._current_name == name:
            return
        # Oculta actual
        if self._current_name is not None:
            self._screens[self._current_name].pack_forget()

        # Muestra nueva
        self._current_name = name
        screen = self._screens[name]
        screen.pack(fill="both", expand=True)
        screen.on_show()

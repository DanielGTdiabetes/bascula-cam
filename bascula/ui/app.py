# -*- coding: utf-8 -*-
import tkinter as tk
from tkinter import ttk

from utils import save_config
from bascula.ui.screens import HomeScreen, SettingsScreen
from serial_reader import SerialReader
from tare_manager import TareManager
from utils import MovingAverage

class BasculaAppTk:
    """ Orquestador Tk: servicios y navegación entre Home y Ajustes. """
    def __init__(self, root: tk.Tk, cfg: dict):
        self.root = root
        self.cfg = cfg

        # Ventana
        self.root.title("Báscula Digital Pro")
        self.root.attributes("-fullscreen", True)
        self.root.configure(bg="#0f1115")

        # ttk theme
        style = ttk.Style(self.root)
        try: style.theme_use("clam")
        except tk.TclError: pass

        # Servicios
        self.reader = None
        self.tare = TareManager(calib_factor=self.cfg.get("calib_factor",1.0), min_display=0.0)
        self.smoother = MovingAverage(size=self.cfg.get("smoothing",5))

        # Serie
        try:
            self.reader = SerialReader(
                port=self.cfg.get("port","/dev/serial0"),
                baud=self.cfg.get("baud",115200)
            )
            self.reader.start()
        except Exception as e:
            print(f"[SERIE] No se pudo abrir {self.cfg.get('port')} @ {self.cfg.get('baud')}: {e}", flush=True)

        # Contenedor y pantallas
        self._container = tk.Frame(self.root, bg="#0f1115")
        self._container.pack(fill="both", expand=True)

        self._screens = {}
        self._current_name = None

        self._screens["home"] = HomeScreen(self._container, self, on_open_settings=lambda: self.navigate("settings"))
        self._screens["settings"] = SettingsScreen(self._container, self, on_back=lambda: self.navigate("home"))

        self.navigate("home")

        # Atajos
        self.root.bind("<Escape>", lambda e: self.root.destroy())

    # API para pantallas
    def get_reader(self): return self.reader
    def get_tare(self): return self.tare
    def get_smoother(self): return self.smoother
    def get_cfg(self): return self.cfg
    def save_cfg(self): save_config(self.cfg)

    # Navegación
    def navigate(self, name: str):
        if self._current_name == name: return
        if self._current_name is not None:
            self._screens[self._current_name].pack_forget()
        self._current_name = name
        screen = self._screens[name]
        screen.pack(fill="both", expand=True)
        screen.on_show()

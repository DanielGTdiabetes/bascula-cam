# -*- coding: utf-8 -*-
"""
app.py (Versión Definitiva y Completa)
--------------------------------------
Cerebro de la aplicación que integra los servicios REALES (cámara y báscula)
con la interfaz de usuario avanzada y completa.
"""
import os
import time
import random
import tkinter as tk
import logging

# --- Importaciones de todos los componentes de la aplicación ---
from bascula.services.camera import CameraService
from serial_reader import SerialReader
from tare_manager import TareManager
from utils import load_config, save_config, MovingAverage
from bascula.ui.screens import HomeScreen, SettingsMenuScreen, CalibScreen, WifiScreen, ApiKeyScreen

class BasculaAppTk:
    def __init__(self) -> None:
        self.root = tk.Tk(); self.root.title("Báscula Digital Pro")
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        try:
            self.root.overrideredirect(True)
            self.root.configure(cursor="none")
        except tk.TclError:
            logging.warning("No se pudo ocultar la barra de título o el cursor.")
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Escape>", lambda e: self._on_close())

        self._init_services()
        self._build_ui()
        self.root.focus_force()

    def _init_services(self):
        """Inicializa los servicios de báscula y CÁMARA REAL."""
        self.cfg = load_config()
        
        try:
            self.reader = SerialReader(port=self.cfg.get("port","/dev/serial0"), baud=self.cfg.get("baud",115200))
            self.tare = TareManager(calib_factor=self.cfg.get("calib_factor",1.0))
            self.smoother = MovingAverage(size=self.cfg.get("smoothing",5))
            self.reader.start()
            logging.info("Servicio de báscula iniciado.")
        except Exception as e:
            logging.error(f"Error al iniciar servicios de báscula: {e}")
            self.reader = None; self.tare = TareManager(); self.smoother = MovingAverage()

        self.camera = CameraService(width=800, height=480, fps=15)
        if self.camera.is_available():
            logging.info(f"Servicio de cámara listo. Backend: {self.camera.backend_name()}")
        else:
            logging.warning(f"Cámara NO disponible: {self.camera.reason_unavailable()}")

    def _build_ui(self):
        """Crea y gestiona el apilamiento de las pantallas."""
        self.main = tk.Frame(self.root, bg="#0a0e1a"); self.main.pack(fill="both", expand=True)
        self.screens = {}
        
        screen_map = {"home": HomeScreen, "settingsmenu": SettingsMenuScreen, "calib": CalibScreen, "wifi": WifiScreen, "apikey": ApiKeyScreen}
        for name, ScreenClass in screen_map.items():
            # Pasa el callback a HomeScreen para que pueda abrir el menú de ajustes
            if ScreenClass == HomeScreen:
                screen = ScreenClass(self.main, self, on_open_settings_menu=lambda: self.show_screen("settingsmenu"))
            else:
                screen = ScreenClass(self.main, self)
            self.screens[name] = screen
        
        self.show_screen("home")

    def show_screen(self, name: str):
        """Muestra una pantalla por su nombre, ocultando las demás."""
        for screen in self.screens.values():
            screen.pack_forget()
        
        screen_to_show = self.screens.get(name)
        if screen_to_show:
            screen_to_show.pack(fill="both", expand=True)
            if hasattr(screen_to_show, "on_show"):
                screen_to_show.on_show()

    def _on_close(self):
        logging.info("Cerrando aplicación...");
        try:
            if self.reader: self.reader.stop()
            if self.camera: self.camera.stop()
        finally:
            self.root.quit(); self.root.destroy(); import sys; sys.exit(0)

    # --- API para que las pantallas accedan a los servicios ---
    def get_cfg(self): return self.cfg
    def save_cfg(self): save_config(self.cfg)
    def get_reader(self): return self.reader
    def get_tare(self): return self.tare
    
    def get_latest_weight(self):
        if self.reader:
            raw = self.reader.get_latest()
            if raw is not None:
                smoothed = self.smoother.add(raw)
                return self.tare.compute_net(smoothed)
        return 0.0

    def capture_image(self):
        if not self.camera or not self.camera.is_available():
            raise RuntimeError("El servicio de cámara no está operativo.")
        capture_dir = os.path.expanduser("~/captures")
        os.makedirs(capture_dir, exist_ok=True)
        filepath = os.path.join(capture_dir, f"capture_{int(time.time())}.jpg")
        return self.camera.capture_photo(filepath)

    def request_nutrition(self, image_path, grams):
        # Stub/simulación de la respuesta de la API de nutrición
        name = random.choice(["Manzana", "Plátano", "Naranja"])
        factors = {"Manzana": 0.52, "Plátano": 0.89, "Naranja": 0.47}
        return {"name": name, "grams": grams, "kcal": grams * factors[name], "carbs": grams * 0.15, "protein": grams * 0.01, "fat": grams * 0.002}

    def wifi_scan(self):
        # Stub para escanear redes
        return ["Intek_5G", "Intek_2G", "Casa_Dani", "Invitados", "Orange-1234"]

    def run(self):
        self.root.mainloop()

def run(): # Función de alias para compatibilidad
    app = BasculaAppTk()
    app.run()

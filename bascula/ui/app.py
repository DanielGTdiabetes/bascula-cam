# -*- coding: utf-8 -*-
"""
app.py
------
Versión final que fusiona la UI avanzada con el CameraService funcional.
Este archivo actúa como el "cerebro" de la aplicación.
"""
import os
import time
import random
import tkinter as tk
import logging

# --- Componentes de la aplicación ---
# Servicios reales
from bascula.services.camera import CameraService
from serial_reader import SerialReader
from tare_manager import TareManager
from utils import load_config, save_config, MovingAverage

# Pantallas de la UI avanzada
from bascula.ui.screens import HomeScreen, SettingsMenuScreen, CalibScreen, WifiScreen, ApiKeyScreen

class BasculaAppTk:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Báscula Digital Pro")

        # --- Configuración de la ventana (de tu app antigua) ---
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        try:
            self.root.overrideredirect(True)
            self.root.configure(cursor="none")
        except tk.TclError:
            logging.warning("No se pudo ocultar la barra de título o el cursor.")
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Escape>", lambda e: self._on_close())

        # --- Inicialización de Servicios ---
        self._init_services()

        # --- Construcción y gestión de la UI (de tu app antigua) ---
        self._build_ui()
        self.root.focus_force()

    def _init_services(self):
        """Inicializa los servicios reales: Báscula y Cámara."""
        self.cfg = load_config()
        
        # Servicios de la báscula (de tu app antigua)
        try:
            self.reader = SerialReader(port=self.cfg.get("port", "/dev/serial0"), baud=self.cfg.get("baud", 115200))
            self.tare = TareManager(calib_factor=self.cfg.get("calib_factor", 1.0))
            self.smoother = MovingAverage(size=self.cfg.get("smoothing", 5))
            self.reader.start()
        except Exception as e:
            logging.error(f"Error al inicializar servicios de báscula: {e}")
            self.reader = None
            self.tare = TareManager()
            self.smoother = MovingAverage()
            
        # ¡IMPORTANTE! Servicio de cámara real (de la nueva versión)
        self.camera = CameraService(width=800, height=480, fps=15)
        if self.camera.is_available():
            self.camera.start()
            logging.info(f"Cámara iniciada con backend: {self.camera.backend_name()}")
        else:
            logging.warning(f"Cámara no disponible: {self.camera.reason_unavailable()}")

    def _build_ui(self):
        """Crea y gestiona las múltiples pantallas de la UI."""
        self.main = tk.Frame(self.root, bg="#0a0e1a")
        self.main.pack(fill="both", expand=True)
        self.screens = {}
        
        # Creación de todas tus pantallas
        for ScreenClass in (HomeScreen, SettingsMenuScreen, CalibScreen, WifiScreen, ApiKeyScreen):
            name_lower = ScreenClass.__name__.lower().replace("screen", "")
            # Pasa el callback a HomeScreen para abrir el menú
            if ScreenClass == HomeScreen:
                screen = ScreenClass(self.main, self, on_open_settings_menu=lambda: self.show_screen("settingsmenu"))
            else:
                screen = ScreenClass(self.main, self)
            self.screens[name_lower] = screen
        
        self.show_screen("home")

    def show_screen(self, name: str):
        """Muestra una pantalla por su nombre y la trae al frente."""
        # Olvida la pantalla actual si existe
        for screen in self.screens.values():
            screen.pack_forget()
        
        # Muestra la nueva pantalla
        screen_to_show = self.screens.get(name)
        if screen_to_show:
            screen_to_show.pack(fill="both", expand=True)
            screen_to_show.tkraise()
            if hasattr(screen_to_show, "on_show"):
                screen_to_show.on_show()

    def _on_close(self):
        """Detiene los servicios de forma segura antes de cerrar."""
        logging.info("Cerrando aplicación...")
        try:
            if self.reader: self.reader.stop()
            if self.camera: self.camera.stop()
        except Exception as e:
            logging.error(f"Error durante el cierre: {e}")
        finally:
            self.root.quit()
            self.root.destroy()
            import sys; sys.exit(0)

    # ===== API para que las pantallas accedan a los servicios =====
    def get_cfg(self) -> dict: return self.cfg
    def save_cfg(self) -> None: save_config(self.cfg)
    def get_reader(self): return self.reader
    def get_tare(self): return self.tare
    def get_smoother(self): return self.smoother

    def get_latest_weight(self) -> float:
        """Calcula el último peso neto suavizado."""
        try:
            if self.reader:
                raw = self.reader.get_latest()
                if raw is not None:
                    sm = self.smoother.add(raw)
                    return self.tare.compute_net(sm)
            return 0.0
        except Exception: return 0.0

    def capture_image(self) -> str:
        """
        ¡IMPORTANTE! Usa el servicio de cámara real para capturar una foto.
        """
        if not self.camera or not self.camera.is_available():
            raise RuntimeError("El servicio de cámara no está disponible.")
        
        capture_dir = "captures"
        os.makedirs(capture_dir, exist_ok=True)
        filename = f"capture_{int(time.time())}.jpg"
        filepath = os.path.join(capture_dir, filename)
        
        # Llama al método del servicio de cámara real
        return self.camera.capture_photo(filepath)

    # --- Stubs (se mantienen igual por ahora) ---
    def request_nutrition(self, image_path: str, grams: float) -> dict:
        name = random.choice(["Manzana", "Plátano", "Analizado"])
        factors = {"Manzana": {"kcal_g": 0.52}, "Plátano": {"kcal_g": 0.89}, "Analizado": {"kcal_g": 1.2}}
        g = max(0.0, grams or 0.0)
        return {"name": name, "grams": g, "kcal": g * factors[name]["kcal_g"], "carbs": g*0.2, "protein":g*0.1, "fat":g*0.05}

    def run(self) -> None:
        self.root.mainloop()

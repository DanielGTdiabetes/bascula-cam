# -*- coding: utf-8 -*-
import os
import time
import random
import tkinter as tk
import logging

from serial_reader import SerialReader
from tare_manager import TareManager
from utils import load_config, save_config, MovingAverage

# Cámara opcional (no tocamos si ya la tienes)
try:
    from bascula.services.camera import CameraService
except Exception:
    CameraService = None

# Tus pantallas existentes
from bascula.ui.screens import HomeScreen, SettingsMenuScreen, CalibScreen, WifiScreen, ApiKeyScreen

class BasculaAppTk:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Báscula Digital Pro")
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        try:
            self.root.overrideredirect(True)
            self.root.configure(cursor="none")
        except tk.TclError:
            logging.warning("No se pudo ocultar la barra de título o el cursor.")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Escape>", lambda e: self._on_close())

        self._last_weight_raw = None   # último bruto del lector
        self._last_weight_net = 0.0    # último mostrado (neto)
        self._last_weight_ts = 0.0     # tiempo del último bruto
        self._stable_threshold = 0.5   # histeresis simple

        self._init_services()
        self._build_ui()
        self.root.focus_force()

    def _init_services(self):
        self.cfg = load_config()
        # Lector serie robusto (no consume lecturas)
        try:
            self.reader = SerialReader(port=self.cfg.get("port","/dev/serial0"),
                                       baud=self.cfg.get("baud",115200),
                                       stale_ms=self.cfg.get("stale_ms", 800))
            self.reader.start()
            logging.info("Servicio de báscula iniciado.")
        except Exception as e:
            logging.error(f"Error al iniciar servicios de báscula: {e}")
            self.reader = None

        # Tara y suavizado
        self.tare = TareManager(calib_factor=self.cfg.get("calib_factor",1.0))
        self.smoother = MovingAverage(size=self.cfg.get("smoothing",5))

        # Cámara (si existe)
        self.camera = None
        if CameraService is not None:
            try:
                self.camera = CameraService(width=800, height=480, fps=15)
                if getattr(self.camera, "is_available", lambda: False)():
                    logging.info(f"Servicio de cámara listo. Backend: {self.camera.backend_name()}")
                else:
                    logging.warning(f"Cámara NO disponible: {self.camera.reason_unavailable()}")
            except Exception as e:
                logging.warning(f"No se pudo inicializar la cámara: {e}")

    def _build_ui(self):
        self.main = tk.Frame(self.root, bg="#0a0e1a")
        self.main.pack(fill="both", expand=True)
        self.screens = {}

        screen_map = {
            "home": HomeScreen,
            "settingsmenu": SettingsMenuScreen,
            "calib": CalibScreen,
            "wifi": WifiScreen,
            "apikey": ApiKeyScreen
        }
        for name, ScreenClass in screen_map.items():
            if ScreenClass == HomeScreen:
                screen = ScreenClass(self.main, self, on_open_settings_menu=lambda: self.show_screen("settingsmenu"))
            else:
                screen = ScreenClass(self.main, self)
            self.screens[name] = screen
        self.show_screen("home")

    def show_screen(self, name: str):
        # Soporte on_hide/on_show para evitar timers colgados
        for screen in self.screens.values():
            if hasattr(screen, "on_hide"):
                try: screen.on_hide()
                except Exception: pass
            screen.pack_forget()
        screen_to_show = self.screens.get(name)
        if screen_to_show:
            screen_to_show.pack(fill="both", expand=True)
            if hasattr(screen_to_show, "on_show"):
                try: screen_to_show.on_show()
                except Exception: pass

    def _on_close(self):
        logging.info("Cerrando aplicación…")
        try:
            if self.reader: self.reader.stop()
            if self.camera and hasattr(self.camera, "stop"): self.camera.stop()
        finally:
            self.root.quit()
            self.root.destroy()
            import sys; sys.exit(0)

    # --- API para pantallas ---
    def get_cfg(self): return self.cfg
    def save_cfg(self): save_config(self.cfg)
    def get_reader(self): return self.reader
    def get_tare(self): return self.tare

    def get_latest_weight(self):
        """
        Devuelve el peso NETO para mostrar, con anti-parpadeo:
        - Si la lectura serie es None (stale), NO devuelve 0: mantiene el último valor mostrado.
        - Aplica MovingAverage + tara + factor de calibración.
        - Histeresis: ignora micro-variaciones < threshold para evitar "saltos".
        """
        raw = None
        if self.reader:
            raw = self.reader.get_latest()

        if raw is not None:
            self._last_weight_raw = raw
            self._last_weight_ts = time.time()
            smoothed = self.smoother.add(raw)
            net = self.tare.compute_net(smoothed)
            # Histeresis simple: si la variación es muy pequeña, mantener valor
            if abs(net - self._last_weight_net) < self._stable_threshold:
                return self._last_weight_net
            self._last_weight_net = net
            return net
        else:
            # Sin dato nuevo: NO devolver 0; mantenemos el último valor mostrado
            return self._last_weight_net

    def capture_image(self):
        if not self.camera or not getattr(self.camera, "is_available", lambda: False)():
            raise RuntimeError("El servicio de cámara no está operativo.")
        capture_dir = os.path.expanduser("~/captures")
        os.makedirs(capture_dir, exist_ok=True)
        path = os.path.join(capture_dir, f"capture_{int(time.time())}.jpg")
        return self.camera.capture_photo(path)

    def request_nutrition(self, image_path, grams):
        # Placeholder (tu lógica real de nutrición)
        name = random.choice(["Manzana", "Plátano", "Naranja"])
        factors = {"Manzana": 0.52, "Plátano": 0.89, "Naranja": 0.47}
        return {"name": name, "grams": grams, "kcal": grams * factors[name], "carbs": grams * 0.15, "protein": grams * 0.01, "fat": grams * 0.002}

    def wifi_scan(self):
        return ["Intek_5G", "Intek_2G", "Casa_Dani", "Invitados", "Orange-1234"]

    def run(self):
        self.root.mainloop()

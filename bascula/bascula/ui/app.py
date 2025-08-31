# -*- coding: utf-8 -*-
import os, time, threading, logging, tkinter as tk
import sys
from utils import load_config, save_config, MovingAverage
from tare_manager import TareManager
from serial_reader import SerialReader
from bascula.ui.splash import SplashScreen
from bascula.ui.screens import HomeScreen, SettingsMenuScreen, CalibScreen, WifiScreen, ApiKeyScreen
from bascula.services.photo_manager import PhotoManager

try:
    from bascula.services.camera import CameraService
except Exception as e:
    CameraService = None
    logging.error(f"Fallo al importar CameraService: {e}")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
log = logging.getLogger("bascula")

class BasculaAppTk:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("Báscula Digital Pro")
        self.root.configure(bg="#0a0e1a")
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{sw}x{sh}+0+0")
        try:
            self.root.overrideredirect(True)
            self.root.configure(cursor="none")
        except tk.TclError:
            log.warning("No se pudo ocultar la barra de título o el cursor.")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Escape>", lambda e: self._on_close())

        self._last_weight_net = 0.0
        self.splash = SplashScreen(self.root, subtitle="Inicializando servicios…")
        self.root.update()

        self.cfg = None
        self.reader = None
        self.tare = None
        self.smoother = None
        self.camera = None
        self.photo_manager = None

        t = threading.Thread(target=self._init_services_bg, daemon=True)
        t.start()

    def _init_services_bg(self):
        try:
            self.splash.set_status("Cargando configuración")
            self.cfg = load_config()
            self.splash.set_status("Iniciando báscula")
            self.reader = SerialReader(port=self.cfg.get("port", "/dev/serial0"), baud=self.cfg.get("baud", 115200))
            self.reader.start()
            self.splash.set_status("Aplicando tara y suavizado")
            self.tare = TareManager(calib_factor=self.cfg.get("calib_factor", 1.0))
            self.smoother = MovingAverage(size=self.cfg.get("smoothing", 5))

            if CameraService is not None:
                self.splash.set_status("Abriendo cámara")
                try:
                    self.camera = CameraService(width=800, height=480, fps=15)
                    log.info("Estado de la cámara: %s", self.camera.explain_status())
                except Exception as e:
                    log.error("Fallo CRÍTICO al inicializar la cámara: %s", e)
            
            if hasattr(self, "camera") and self.camera and self.camera.picam:
                self.photo_manager = PhotoManager(logger=log)
                self.photo_manager.attach_camera(self.camera.picam)
                log.info("PhotoManager adjuntado a la cámara.")
            
            time.sleep(0.35)
        finally:
            self.root.after(0, self._on_services_ready)

    def _on_services_ready(self):
        self._build_ui()
        self.splash.close()
        self.root.deiconify()
        self.root.focus_force()

    def _build_ui(self):
        self.main = tk.Frame(self.root, bg="#0a0e1a")
        self.main.pack(fill="both", expand=True)
        self.screens = {}
        screen_map = {
            "home": HomeScreen, "settingsmenu": SettingsMenuScreen,
            "calib": CalibScreen, "wifi": WifiScreen, "apikey": ApiKeyScreen,
        }
        for name, ScreenClass in screen_map.items():
            if name == "home":
                screen = ScreenClass(self.main, self, on_open_settings_menu=lambda: self.show_screen("settingsmenu"))
            else:
                screen = ScreenClass(self.main, self)
            self.screens[name] = screen
        self.show_screen("home")

    def show_screen(self, name: str):
        for screen in self.screens.values():
            if hasattr(screen, "on_hide"): screen.on_hide()
            screen.pack_forget()
        target = self.screens.get(name)
        if target:
            target.pack(fill="both", expand=True)
            if hasattr(target, "on_show"): target.on_show()

    def _on_close(self):
        log.info("Cerrando aplicación…")
        if self.camera: self.camera.stop()
        if self.reader: self.reader.stop()
        self.root.quit()
        self.root.destroy()
        sys.exit(0)

    def get_cfg(self): return self.cfg
    def save_cfg(self): save_config(self.cfg)
    def get_reader(self): return self.reader
    def get_tare(self): return self.tare

    def get_latest_weight(self):
        raw = self.reader.get_latest() if self.reader else None
        if raw is not None:
            smoothed = self.smoother.add(raw)
            self._last_weight_net = self.tare.compute_net(smoothed)
        return self._last_weight_net
    
    def capture_image(self, label: str = "add_item"):
        if not self.camera or not self.camera.available():
            raise RuntimeError("Cámara no operativa para capturar.")
        # La nueva clase CameraService gestiona la captura de forma robusta
        return self.camera.capture_still()

    def delete_image(self, path: str):
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception as e:
            log.warning(f"No se pudo borrar imagen temporal: {e}")

    def request_nutrition(self, image_path: str, weight: float):
        log.info(f"Simulando reconocimiento para {image_path} con peso {weight:.2f}g")
        time.sleep(1.5)
        return {"name": "Alimento de prueba", "grams": weight, "kcal": round(weight * 1.2, 1),
                "carbs": round(weight * 0.15, 1), "protein": round(weight * 0.05, 1),
                "fat": round(weight * 0.03, 1)}

    def run(self):
        self.root.mainloop()

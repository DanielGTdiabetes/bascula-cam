# -*- coding: utf-8 -*-
import os, time, threading, logging, tkinter as tk
import sys
from utils import load_config, save_config, MovingAverage
from tare_manager import TareManager
from serial_reader import SerialReader
from bascula.ui.splash import SplashScreen
from bascula.ui.screens import HomeScreen, SettingsMenuScreen, CalibScreen, WifiScreen, ApiKeyScreen

# PhotoManager es opcional: si falla el import no debe tumbar la app
try:
    from bascula.services.photo_manager import PhotoManager
except Exception:
    PhotoManager = None

# CameraService también opcional (mantén política de import seguro)
try:
    from bascula.services.camera import CameraService
except Exception:
    CameraService = None

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

        # Estado
        self._last_weight_net = 0.0
        self.cfg = None
        self.reader = None
        self.tare = None
        self.smoother = None
        self.camera = None
        self.photo_manager = None

        # Splash
        self.splash = SplashScreen(self.root, subtitle="Inicializando servicios…")
        self.root.update()

        # Inicialización en background
        t = threading.Thread(target=self._init_services_bg, daemon=True)
        t.start()

    # -------------------- Init servicios --------------------
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

            # Cámara
            if CameraService is not None:
                self.splash.set_status("Abriendo cámara")
                try:
                    self.camera = CameraService(width=800, height=480, fps=15)
                    if getattr(self.camera, "available", None) and self.camera.available():
                        log.info("Cámara lista")
                    else:
                        log.warning("Cámara NO disponible")
                except Exception as e:
                    log.warning("No se pudo inicializar la cámara: %s", e)

            # PhotoManager (si hay Picamera2 dentro de CameraService)
            if PhotoManager is not None and hasattr(self, "camera") and self.camera and hasattr(self.camera, "picam") and self.camera.picam:
                try:
                    self.photo_manager = PhotoManager(logger=log)
                    self.photo_manager.attach_camera(self.camera.picam)
                    log.info("PhotoManager adjuntado.")
                except Exception as e:
                    log.warning("No se pudo adjuntar PhotoManager: %s", e)

            time.sleep(0.35)
        finally:
            self.root.after(0, self._on_services_ready)

    def _on_services_ready(self):
        self._build_ui()
        self.splash.close()
        self.root.deiconify()
        self.root.focus_force()

    # -------------------- UI --------------------
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

    # -------------------- Lifecycle --------------------
    def _on_close(self):
        log.info("Cerrando aplicación…")
        try:
            if self.reader: self.reader.stop()
        except Exception: pass
        try:
            if self.camera and hasattr(self.camera, "stop"): self.camera.stop()
        except Exception: pass
        try:
            self.root.quit()
            self.root.destroy()
        finally:
            sys.exit(0)

    # -------------------- Accesores --------------------
    def get_cfg(self): return self.cfg
    def save_cfg(self): save_config(self.cfg)
    def get_reader(self): return self.reader
    def get_tare(self): return self.tare

    def get_latest_weight(self):
        raw = self.reader.get_latest() if self.reader else None
        if raw is not None:
            smoothed = self.smoother.add(raw)
            self._last_weight_net = self.tare.compute_net(smoothed) if self.tare else smoothed
        return self._last_weight_net

    # -------------------- Fotos efímeras --------------------
    def capture_image(self, label: str = "add_item"):
        # 1) PhotoManager (preferente, borraremos luego con delete_image)
        if self.photo_manager is not None:
            try:
                return str(self.photo_manager.capture(label=label))
            except Exception as e:
                log.warning("Fallo PhotoManager, fallback: %s", e)
        # 2) Fallback a CameraService
        if self.camera and getattr(self.camera, "available", lambda: False)():
            path = f"/tmp/capture_{int(time.time())}.jpg"
            self.camera.capture_still(path)
            return path
        raise RuntimeError("Servicio de cámara no operativo.")

    def delete_image(self, path: str):
        try:
            if not path: return
            if "staging" in path and self.photo_manager is not None:
                from pathlib import Path
                self.photo_manager.mark_used(Path(path))
            elif os.path.exists(path):
                os.remove(path)
        except Exception as e:
            log.warning("No se pudo borrar imagen: %s", e)

    # -------------------- Reconocimiento (stub estable) --------------------
    def request_nutrition(self, image_path: str, weight: float):
        # Placeholder estable hasta integrar API real/visión
        try:
            w = float(weight) if weight is not None else 0.0
        except Exception:
            w = 0.0
        time.sleep(0.4)  # pequeña pausa para UX
        return {
            "name": "Alimento",
            "grams": int(round(max(0.0, w))),
            "kcal": round(w * 1.2, 1),
            "carbs": round(w * 0.15, 1),
            "protein": round(w * 0.05, 1),
            "fat": round(w * 0.03, 1),
        }

    # -------------------- Mainloop --------------------
    def run(self):
        self.root.mainloop()

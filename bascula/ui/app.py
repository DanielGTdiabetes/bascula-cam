# -*- coding: utf-8 -*-
import os, time, threading, logging, tkinter as tk

from utils import load_config, save_config, MovingAverage
from tare_manager import TareManager
from serial_reader import SerialReader

# UI existente (se mantiene)
from bascula.ui.screens import HomeScreen, SettingsMenuScreen, CalibScreen, WifiScreen, ApiKeyScreen
# Splash nuevo
from bascula.ui.splash import SplashScreen

# Cámara opcional
try:
    from bascula.services.camera import CameraService
except Exception:
    CameraService = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
log = logging.getLogger("bascula")

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
            log.warning("No se pudo ocultar la barra de título o el cursor.")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Escape>", lambda e: self._on_close())

        # Estado de peso / estabilidad (anti-parpadeo)
        self._last_weight_raw = None
        self._last_weight_net = 0.0
        self._last_weight_ts  = 0.0
        self._stable_threshold = 0.5  # g

        # 1) Splash y arranque en segundo plano
        self.splash = SplashScreen(self.root, subtitle="Inicializando servicios")
        self.root.update_idletasks()

        self.cfg = None
        self.reader = None
        self.tare = None
        self.smoother = None
        self.camera = None

        t = threading.Thread(target=self._init_services_bg, daemon=True)
        t.start()

    # --- Inicialización en segundo plano (mejora experiencia visual) ---
    def _init_services_bg(self):
        try:
            self.splash.set_status("Cargando configuración")
            self.cfg = load_config()

            # Serie
            self.splash.set_status("Iniciando báscula")
            self.reader = SerialReader(
                port=self.cfg.get("port", "/dev/serial0"),
                baud=self.cfg.get("baud", 115200),
                stale_ms=self.cfg.get("stale_ms", 800)
            )
            self.reader.start()

            # Tara / media móvil
            self.splash.set_status("Aplicando tara y suavizado")
            self.tare = TareManager(calib_factor=self.cfg.get("calib_factor", 1.0))
            self.smoother = MovingAverage(size=self.cfg.get("smoothing", 5))

            # Cámara (opcional) – la abrimos aquí para que el splash la tape
            if CameraService is not None:
                self.splash.set_status("Abriendo cámara")
                try:
                    self.camera = CameraService(width=800, height=480, fps=15)
                    if getattr(self.camera, "is_available", lambda: False)():
                        log.info("Cámara lista: %s", self.camera.backend_name())
                    else:
                        log.warning("Cámara NO disponible: %s", self.camera.reason_unavailable())
                except Exception as e:
                    log.warning("No se pudo inicializar la cámara: %s", e)

            # Pequeña pausa estética (garantiza que el splash quede visible un mínimo)
            time.sleep(0.35)
        finally:
            # Cambiar a UI principal en el hilo de Tk
            self.root.after(0, self._on_services_ready)

    def _on_services_ready(self):
        try:
            self.splash.close()
        except Exception:
            pass
        self._build_ui()
        self.root.focus_force()

    # --- UI (se mantiene tu diseño) ---
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
        for screen in self.screens.values():
            if hasattr(screen, "on_hide"):
                try: screen.on_hide()
                except Exception: pass
            screen.pack_forget()
        target = self.screens.get(name)
        if target:
            target.pack(fill="both", expand=True)
            if hasattr(target, "on_show"):
                try: target.on_show()
                except Exception: pass

    def _on_close(self):
        log.info("Cerrando aplicación…")
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
        Peso neto con anti-parpadeo:
        - Si no hay muestra nueva, mantiene el último valor neto mostrado.
        - Media móvil + tara + umbral de histéresis para estabilidad visual.
        """
        raw = None
        if self.reader:
            raw = self.reader.get_latest()

        if raw is not None:
            self._last_weight_raw = raw
            self._last_weight_ts = time.time()
            smoothed = self.smoother.add(raw)
            net = self.tare.compute_net(smoothed)
            if abs(net - self._last_weight_net) < self._stable_threshold:
                return self._last_weight_net
            self._last_weight_net = net
            return net
        else:
            return self._last_weight_net

    def capture_image(self):
        if not self.camera or not getattr(self.camera, "is_available", lambda: False)():
            raise RuntimeError("El servicio de cámara no está operativo.")
        capture_dir = os.path.expanduser("~/captures")
        os.makedirs(capture_dir, exist_ok=True)
        path = os.path.join(capture_dir, f"capture_{int(time.time())}.jpg")
        return self.camera.capture_photo(path)

    def run(self):
        self.root.mainloop()

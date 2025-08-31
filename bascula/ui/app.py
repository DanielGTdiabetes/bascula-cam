# -*- coding: utf-8 -*-
import os, time, threading, logging, tkinter as tk

from utils import load_config, save_config, MovingAverage
from tare_manager import TareManager
from serial_reader import SerialReader

from bascula.ui.splash import SplashScreen
from bascula.ui.screens import HomeScreen, SettingsMenuScreen, CalibScreen, WifiScreen, ApiKeyScreen
try:
    from bascula.services.photo_manager import PhotoManager
except Exception:
    PhotoManager = None

try:
    from bascula.services.camera import CameraService
except Exception:
    CameraService = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
log = logging.getLogger("bascula")

class BasculaAppTk:
    def __init__(self):
        # Crear root, pero mantenerla oculta hasta que todo esté listo
        self.root = tk.Tk()
        self.root.withdraw()  # <--- importante: ocultar root
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

        # Estado de peso / estabilidad
        self._last_weight_raw = None
        self._last_weight_net = 0.0
        self._last_weight_ts  = 0.0
        self._stable_threshold = 0.5

        # Splash (siempre visible antes de iniciar servicios)
        self.splash = SplashScreen(self.root, subtitle="Inicializando servicios…")
        self.root.update()  # forzar a pintar el splash ya mismo

        # Estructuras que se irán completando
        self.cfg = None
        self.reader = None
        self.tare = None
        self.smoother = None
        self.camera = None

        # Inicio en segundo plano
        t = threading.Thread(target=self._init_services_bg, daemon=True)
        t.start()

    def _init_services_bg(self):
        try:
            self.splash.set_status("Cargando configuración")
            self.cfg = load_config()

            self.splash.set_status("Iniciando báscula")
            self.reader = SerialReader(
                port=self.cfg.get("port", "/dev/serial0"),
                baud=self.cfg.get("baud", 115200),
                stale_ms=self.cfg.get("stale_ms", 800),
            )
            self.reader.start()

            self.splash.set_status("Aplicando tara y suavizado")
            self.tare = TareManager(calib_factor=self.cfg.get("calib_factor", 1.0))
            self.smoother = MovingAverage(size=self.cfg.get("smoothing", 5))

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

            # Integración del gestor de fotos (no reabre la cámara)
            try:
                self.photo_manager = None
                if PhotoManager is not None and hasattr(self, "camera") and self.camera and hasattr(self.camera, "picam") and self.camera.picam:
                    self.photo_manager = PhotoManager(logger=log)
                    self.photo_manager.attach_camera(self.camera.picam)
                    log.info("PhotoManager adjuntado a la cámara existente.")
                else:
                    log.info("PhotoManager no adjuntado (backend no Picamera2 o cámara no disponible).")
            except Exception as e:
                log.warning(f"No se pudo inicializar PhotoManager: {e}")


            # Garantizar que el splash se vea al menos un instante
            time.sleep(0.35)
        finally:
            self.root.after(0, self._on_services_ready)

    
def capture_image(self, label: str = "add_item"):
    """Captura una imagen de forma efímera.
    - Si hay PhotoManager adjunto (Picamera2), guarda en ~/.bascula/photos/staging y devuelve la ruta.
    - Si no, usa el backend actual de CameraService guardando temporalmente en ~/captures.
    Nota: la imagen se debe borrar tras usarse llamando a delete_image(path).
    """
    # Intento 1: PhotoManager con Picamera2
    if PhotoManager is not None and getattr(self, "photo_manager", None) is not None:
        try:
            p = self.photo_manager.capture(label=label)
            return str(p)
        except Exception as e:
            log.warning(f"PhotoManager fallo en captura, fallback a CameraService: {e}")
    # Fallback estable: CameraService -> ~/captures
    if not self.camera or not getattr(self.camera, "is_available", lambda: False)():
        raise RuntimeError("El servicio de cámara no está operativo.")
    capture_dir = os.path.expanduser("~/captures")
    os.makedirs(capture_dir, exist_ok=True)
    path = os.path.join(capture_dir, f"capture_{int(time.time())}.jpg")
    self.camera.capture_photo(path)
    return path

def delete_image(self, path: str):
    """Borra la imagen de forma segura, tanto si es de PhotoManager como si es del fallback."""
    try:
        if not path:
            return
        # Si es del PhotoManager (dentro de ~/.bascula/photos/staging), borra con mark_used
        home = os.path.expanduser("~")
        staging_prefix = os.path.join(home, ".bascula", "photos", "staging") + os.sep
        if path.startswith(staging_prefix) and getattr(self, "photo_manager", None) is not None:
            try:
                from pathlib import Path
                self.photo_manager.mark_used(Path(path))
                return
            except Exception as e:
                log.warning(f"Fallo borrando con PhotoManager, intento borrar directo: {e}")
        # Borrado directo si no es de PhotoManager
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            log.warning(f"No se pudo borrar imagen temporal: {e}")
    except Exception as e:
        log.warning(f"delete_image() error inesperado: {e}")

    def request_nutrition(self, image_path: str, weight_g: float) -> dict:
        """
        Placeholder estable hasta integrar el reconocimiento real.
        Devuelve un diccionario mínimo con las claves esperadas por la UI.
        No sube la imagen ni hace llamadas de red.
        """
        try:
            grams = 0
            if weight_g is not None:
                try:
                    grams = int(round(float(weight_g)))
                except Exception:
                    grams = 0
            name = "Alimento"
            return {"name": name, "grams": max(0, grams)}
        except Exception as e:
            # Nunca reventar la UI: degradar con valores por defecto
            return {"name": "Alimento", "grams": 0}

    def _on_services_ready(self):
        # Construir la UI principal y mostrar root
        self._build_ui()
        try:
            self.splash.close()
        except Exception:
            pass
        self.root.deiconify()  # <--- mostrar root sólo ahora
        self.root.focus_force()

    def _build_ui(self):
        self.main = tk.Frame(self.root, bg="#0a0e1a")
        self.main.pack(fill="both", expand=True)
        self.screens = {}

        screen_map = {
            "home": HomeScreen,
            "settingsmenu": SettingsMenuScreen,
            "calib": CalibScreen,
            "wifi": WifiScreen,
            "apikey": ApiKeyScreen,
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

    # API para pantallas
    def get_cfg(self): return self.cfg
    def save_cfg(self): save_config(self.cfg)
    def get_reader(self): return self.reader
    def get_tare(self): return self.tare

    def get_latest_weight(self):
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

    


    def run(self):
        self.root.mainloop()
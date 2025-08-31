# -*- coding: utf-8 -*-
"""
Bascula UI - Lista, totales, popups robustos, tema uniforme, reinicio sesión.
"""
import os, time, random
import tkinter as tk
from serial_reader import SerialReader
from tare_manager import TareManager
from utils import load_config, save_config, MovingAverage
from bascula.services.camera import CameraService, CameraError

class BasculaAppTk:
    def __init__(self) -> None:
        self.root = tk.Tk(); self.root.title("Báscula Digital Pro")
        self._fullscreen = os.environ.get("BASCULA_FULLSCREEN","0") in ("1","true","yes")
        self._borderless = os.environ.get("BASCULA_BORDERLESS","1") in ("1","true","yes")
        self._debug = os.environ.get("BASCULA_DEBUG","0") in ("1","true","yes")

        # Ventana
        try:
            import tkinter.font as tkfont
            self._fonts = {
                "huge": tkfont.Font(size=72, weight="bold"),
                "big": tkfont.Font(size=40, weight="bold"),
                "med": tkfont.Font(size=20),
                "small": tkfont.Font(size=14),
            }
        except Exception:
            self._fonts = {}

        sw = self.root.winfo_screenwidth(); sh = self.root.winfo_screenheight()
        if self._borderless:
            try: self.root.overrideredirect(True)
            except Exception: pass
        if self._fullscreen:
            try: self.root.attributes("-fullscreen", True)
            except Exception: pass
        self.root.geometry(f"{sw}x{sh}+0+0"); self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Escape>", lambda e:self._on_close())
        self.root.bind("<Control-q>", lambda e:self._on_close())
        self.root.bind("<F11>", lambda e:self._toggle_borderless())
        self.root.bind("<F1>", lambda e:self._toggle_debug())
        try: self.root.configure(cursor="none")
        except Exception: pass

        self._init_services()
        self._build_ui()

    # -------------------------------------------------------------

    def _init_services(self):
        try:
            self.cfg = load_config()
            self.reader = SerialReader(port=self.cfg.get("port","/dev/serial0"), baud=self.cfg.get("baud",115200))
            self.tare = TareManager(calib_factor=self.cfg.get("calib_factor",1.0))
            self.smoother = MovingAverage(size=self.cfg.get("smoothing",5))

            # Cámara
            try:
                self.camera = CameraService()
                try:
                    self.camera.open()
                except Exception:
                    pass
            except Exception:
                self.camera = None

            self.reader.start()
        except Exception as e:
            print(f"[APP] Error inicializando servicios: {e}")
            self.cfg = {"port":"/dev/serial0","baud":115200,"cal...":1.0,"unit":"g","smoothing":5,"decimals":0,"openai_api_key":""}
            self.reader = None
            self.tare = TareManager(calib_factor=1.0)
            self.smoother = MovingAverage(size=5)

    def _build_ui(self):
        try:
            from bascula.ui.widgets import auto_apply_scaling
            auto_apply_scaling(self.root, target=(1024,600))
        except Exception: pass
        self.main = tk.Frame(self.root, bg="#0a0e1a"); self.main.pack(fill="both", expand=True)
        self.screens = {}; self.current_screen = None

        from bascula.ui.screens import HomeScreen, SettingsMenuScreen, CalibScreen, WifiScreen, ApiKeyScreen

        # Barra superior
        top = tk.Frame(self.main, bg="#0a0e1a"); top.pack(side="top", fill="x")
        self.title_lbl = tk.Label(top, text="BÁSCULA DIGITAL PRO", fg="#d6e1ff", bg="#0a0e1a", font=self._fonts.get("med"))
        self.title_lbl.pack(side="left", padx=16, pady=8)
        btn_settings = tk.Button(top, text="⚙ Ajustes", command=lambda:self.show_screen("settings"))
        btn_settings.pack(side="right", padx=8, pady=8)

        # Cuerpo: contenedor de pantallas
        self.container = tk.Frame(self.main, bg="#0a0e1a")
        self.container.pack(side="top", fill="both", expand=True)

        # Instanciar pantallas
        self.screens["home"] = HomeScreen(self.container, self)
        self.screens["settings"] = SettingsMenuScreen(self.container, self)
        self.screens["calib"] = CalibScreen(self.container, self)
        self.screens["wifi"] = WifiScreen(self.container, self)
        self.screens["apikey"] = ApiKeyScreen(self.container, self)

        self.show_screen("home")

    def show_screen(self, name: str) -> None:
        if self.current_screen:
            try: self.current_screen.pack_forget()
            except Exception: pass
        scr = self.screens.get(name)
        if not scr: return
        try:
            scr.pack(fill="both", expand=True)
            self.current_screen = scr
            try: scr.on_show()
            except Exception: pass
        except Exception:
            self.current_screen = None

    # -------------------------------------------------------------
    # Atajos públicos que usan tus pantallas (HomeScreen, etc.)

    def get_weight(self) -> float:
        try:
            if self.reader:
                raw = self.reader.get_weight()
                if raw is not None:
                    sm = self.smoother.add(raw); return self.tare.compute_net(sm)
            return 0.0
        except Exception: return 0.0

    def capture_image(self) -> str:
        """
        Captura una foto con la cámara y devuelve la ruta al JPEG.
        Lanza CameraError si no es posible capturar.
        """
        if not hasattr(self, "camera") or self.camera is None:
            self.camera = CameraService()
        if not self.camera.is_open():
            self.camera.open()
        return self.camera.capture_jpeg()

    def request_nutrition(self, image_path: str, grams: float) -> dict:
        name = random.choice(["Manzana","Plátano","Desconocido"])
        factors = {
            "Manzana": {"kcal":0.52,"carbs":0.14,"protein":0.003,"fat":0.002},
            "Plátano": {"kcal":0.89,"carbs":0.23,"protein":0.011,"fat":0.003},
            "Desconocido": {"kcal":0.7,"carbs":0.15,"protein":0.01,"fat":0.01},
        }.get(name, {"kcal":0.7,"carbs":0.15,"protein":0.01,"fat":0.01})
        g = max(grams, 0.0)
        return {
            "name": name,
            "kcal": round(factors["kcal"] * g, 1),
            "carbs": round(factors["carbs"] * g, 1),
            "protein": round(factors["protein"] * g, 1),
            "fat": round(factors["fat"] * g, 1),
        }

    def wifi_connect(self, ssid: str, password: str) -> bool:
        return False
    def wifi_scan(self) -> list:
        return []

    # -------------------------------------------------------------

    def _toggle_borderless(self):
        self._borderless = not self._borderless
        try: self.root.overrideredirect(self._borderless)
        except Exception: pass

    def _toggle_debug(self):
        self._debug = not self._debug
        print(f"[DEBUG] {self._debug}")

    def _on_close(self):
        try:
            self.root.quit()
        except Exception:
            pass

    def run(self) -> None:
        try:
            sw = self.root.winfo_screenwidth(); sh = self.root.winfo_screenheight()
            self.root.geometry(f"{sw}x{sh}+0+0")
            self.root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            # Cerrar cámara y parar lector serie
            try:
                if hasattr(self, "camera") and self.camera:
                    try: self.camera.close()
                    except Exception: pass
            except Exception: pass
            try:
                if self.reader: self.reader.stop()
            except Exception: pass

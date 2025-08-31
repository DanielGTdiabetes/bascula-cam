# -*- coding: utf-8 -*-
"""
Bascula UI - Lista, totales, popups robustos, tema uniforme, reinicio sesión.
"""
import os, time, random
import tkinter as tk
from serial_reader import SerialReader
from tare_manager import TareManager
from utils import load_config, save_config, MovingAverage

class BasculaAppTk:
    def __init__(self) -> None:
        self.root = tk.Tk(); self.root.title("Báscula Digital Pro")
        self._fullscreen = os.environ.get("BASCULA_FULLSCREEN","0") in ("1","true","yes")
        self._borderless = os.environ.get("BASCULA_BORDERLESS","1") in ("1","true","yes")
        self._debug = os.environ.get("BASCULA_DEBUG","0") in ("1","true","yes")
        self.root.update_idletasks()
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
        self._overlay = None
        if self._debug:
            self._overlay = self._build_overlay(); self._tick_overlay()
        self.root.focus_force(); self.root.update_idletasks(); self.root.geometry(f"{sw}x{sh}+0+0"); self.root.lift()

    def _init_services(self):
        try:
            self.cfg = load_config()
            self.reader = SerialReader(port=self.cfg.get("port","/dev/serial0"), baud=self.cfg.get("baud",115200))
            self.tare = TareManager(calib_factor=self.cfg.get("calib_factor",1.0))
            self.smoother = MovingAverage(size=self.cfg.get("smoothing",5))
            self.reader.start()
        except Exception as e:
            print(f"[APP] Error inicializando servicios: {e}")
            self.cfg = {"port":"/dev/serial0","baud":115200,"calib_factor":1.0,"unit":"g","smoothing":5,"decimals":0,"openai_api_key":""}
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
        self.screens["home"] = HomeScreen(self.main, self, on_open_settings_menu=lambda:self.show_screen("settings_menu"))
        self.screens["settings_menu"] = SettingsMenuScreen(self.main, self)
        self.screens["calib"] = CalibScreen(self.main, self)
        self.screens["wifi"] = WifiScreen(self.main, self)
        self.screens["apikey"] = ApiKeyScreen(self.main, self)
        self.show_screen("home")

    def show_screen(self, name: str):
        if hasattr(self, "current_screen") and self.current_screen:
            if hasattr(self.current_screen, "on_hide"): self.current_screen.on_hide()
            self.current_screen.pack_forget()
        screen = self.screens.get(name)
        if screen:
            screen.pack(fill="both", expand=True); self.current_screen = screen
            if hasattr(screen, "on_show"): screen.on_show()

    def _build_overlay(self) -> tk.Label:
        ov = tk.Label(self.root, text="", bg="#000000", fg="#00ff00", font=("monospace",10), justify="left", anchor="nw")
        ov.place(x=5, y=5); return ov
    def _tick_overlay(self):
        if not self._overlay: return
        try:
            sw = self.root.winfo_screenwidth(); sh = self.root.winfo_screenheight()
            ww = self.root.winfo_width(); wh = self.root.winfo_height()
            weight = self.get_latest_weight(); reader_status = "OK" if self.reader else "ERROR"
            txt = f"Screen: {sw}x{sh}\nWindow: {ww}x{wh}\nWeight: {weight:.2f}g\nReader: {reader_status}\nBorderless:{self._borderless}\nFullscreen:{self._fullscreen}"
            self._overlay.config(text=txt)
        except Exception as e:
            self._overlay.config(text=f"Debug Error: {e}")
        self.root.after(1000, self._tick_overlay)
    def _toggle_borderless(self):
        self._borderless = not self._borderless
        try: self.root.overrideredirect(self._borderless)
        except Exception: pass
    def _toggle_debug(self):
        self._debug = not self._debug
        if self._debug and not self._overlay:
            self._overlay = self._build_overlay(); self._tick_overlay()
        elif not self._debug and self._overlay:
            self._overlay.destroy(); self._overlay = None
    def _on_close(self):
        try:
            if self._overlay:
                try: self._overlay.destroy()
                except Exception: pass
            if self.reader: self.reader.stop()
            self.root.quit(); self.root.destroy()
        except Exception as e:
            print(f"[APP] Error cierre: {e}")
        finally:
            import sys; sys.exit(0)

    # ===== API para pantallas =====
    def get_cfg(self) -> dict: return self.cfg
    def save_cfg(self) -> None:
        try: save_config(self.cfg)
        except Exception as e: print(f"[APP] Error guardando config: {e}")
    def get_reader(self): return self.reader
    def get_tare(self): return self.tare
    def get_smoother(self): return self.smoother

    def get_latest_weight(self) -> float:
        try:
            if self.reader:
                raw = self.reader.get_latest()
                if raw is not None:
                    sm = self.smoother.add(raw); return self.tare.compute_net(sm)
            return 0.0
        except Exception: return 0.0

    # ===== Funciones de la aplicación =====
    def capture_image(self) -> str:
        """
        Captura una imagen mediante la cámara real si está disponible.
        Si hay un problema, se crea un archivo vacío y se muestra un error.
        """
        try:
            from bascula.services.camera import CameraService
            cam = CameraService(width=800, height=600)
            if not cam.available():
                raise Exception("Cámara no disponible")
            
            image_path = cam.capture_still()
            cam.stop()
            return image_path
        except Exception as e:
            print(f"[APP] Error captura real: {e}")
            fake_path = f"/tmp/capture_{int(time.time())}.jpg"
            try:
                with open(fake_path, "wb") as f:
                    f.write(b"")
            except Exception:
                pass
            return fake_path

    def request_nutrition(self, image_path: str, grams: float) -> dict:
        name = random.choice(["Manzana","Plátano","Desconocido"])
        factors = {
            "Manzana": {"kcal_g":0.52, "carbs_g":0.14, "protein_g":0.003, "fat_g":0.002},
            "Plátano": {"kcal_g":0.89, "carbs_g":0.23, "protein_g":0.011, "fat_g":0.003},
            "Desconocido": {"kcal_g":0.80, "carbs_g":0.15, "protein_g":0.010, "fat_g":0.010},
        }
        f = factors[name]; g = max(0.0, grams or 0.0)
        return {"name": name, "grams": g, "kcal": g*f["kcal_g"], "carbs": g*f["carbs_g"], "protein": g*f["protein_g"], "fat": g*f["fat_g"], "image_path": image_path}

    def wifi_connect(self, ssid: str, psk: str) -> bool:
        print(f"[APP] wifi_connect -> SSID='{ssid}' (stub)"); return False
    def wifi_scan(self):
        print("[APP] wifi_scan solicitado (stub)")
        return ["Intek_5G","Intek_2G","Casa_Dani","Invitados","Orange-1234"]

    def run(self) -> None:
        try:
            sw = self.root.winfo_screenwidth(); sh = self.root.winfo_screenheight()
            self.root.geometry(f"{sw}x{sh}+0+0")
            self.root.mainloop()
        except KeyboardInterrupt:
            pass
        finally:
            try:
                if self.reader: self.reader.stop()
            except Exception: pass

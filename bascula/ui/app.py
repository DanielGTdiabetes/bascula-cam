# -*- coding: utf-8 -*-
"""
Bascula UI - MODIFICADO: Integración de cámara real y backend SerialScale.
"""
import os
import time
import random
import tkinter as tk

# Se reemplaza el lector simple por el backend avanzado
from python_backend.serial_scale import SerialScale
from tare_manager import TareManager
from utils import load_config, save_config, MovingAverage

try:
    from picamera2 import Picamera2, Preview
    PICAMERA_AVAILABLE = True
except (ImportError, RuntimeError):
    PICAMERA_AVAILABLE = False

class BasculaAppTk:
    def __init__(self) -> None:
        self.root = tk.Tk(); self.root.title("Báscula Digital Pro")
        self._fullscreen = os.environ.get("BASCULA_FULLSCREEN","0") in ("1","true","yes")
        self._borderless = os.environ.get("BASCULA_BORDERLESS","1") in ("1","true","yes")
        self._debug = os.environ.get("BASCULA_DEBUG","0") in ("1","true","yes")
        
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        if self._borderless: self.root.overrideredirect(True)
        if self._fullscreen: self.root.attributes("-fullscreen", True)
        
        self.root.geometry(f"{sw}x{sh}+0+0"); self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Escape>", lambda e:self._on_close())
        self.root.bind("<Control-q>", lambda e:self._on_close())
        self.root.bind("<F11>", lambda e:self._toggle_borderless())
        self.root.bind("<F1>", lambda e:self._toggle_debug())
        if not self._debug: self.root.configure(cursor="none")
        
        self.picam2 = None
        self._init_services()
        self._build_ui()
        
        self._overlay = None
        if self._debug:
            self._overlay = self._build_overlay(); self._tick_overlay()
        
        self.root.focus_force(); self.root.lift()

    def _init_services(self):
        try:
            self.cfg = load_config()
            # Se utiliza SerialScale en lugar de SerialReader
            self.reader = SerialScale(port=self.cfg.get("port","/dev/serial0"), baud=self.cfg.get("baud",115200))
            self.tare = TareManager(calib_factor=self.cfg.get("calib_factor",1.0))
            self.smoother = MovingAverage(size=self.cfg.get("smoothing",5))
            
            # El nuevo reader gestiona los datos de peso y estabilidad
            self.last_weight = 0.0
            self.is_stable = False
            self.reader.subscribe(self._update_weight_data)
            self.reader.start()
            
            if PICAMERA_AVAILABLE:
                self.picam2 = Picamera2()
                preview_config = self.picam2.create_preview_configuration(main={"size": (1024, 768)})
                self.picam2.configure(preview_config)
                self.picam2.start()
                print("[APP] Picamera2 inicializada.")
            else:
                print("[APP] WARN: Picamera2 no disponible. Usando captura simulada.")

        except Exception as e:
            print(f"[APP] Error inicializando servicios: {e}")
            self.cfg = {"port":"/dev/serial0","baud":115200,"calib_factor":1.0,"unit":"g","smoothing":5,"decimals":0,"openai_api_key":""}
            self.reader = None
            self.tare = TareManager(calib_factor=1.0)
            self.smoother = MovingAverage(size=5)
    
    def _update_weight_data(self, grams, stable):
        """Callback para recibir datos del SerialScale."""
        # El smoother ya no es necesario aquí, el ESP32 ya filtra.
        self.last_weight = self.tare.compute_net(grams) # Se aplica tara y calibración localmente
        self.is_stable = stable

    def _build_ui(self):
        from bascula.ui.widgets import auto_apply_scaling
        auto_apply_scaling(self.root, target=(1024,600))
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
        if self.current_screen: self.current_screen.pack_forget()
        screen = self.screens.get(name)
        if screen:
            screen.pack(fill="both", expand=True); self.current_screen = screen

    def _build_overlay(self) -> tk.Label:
        ov = tk.Label(self.root, text="", bg="#000000", fg="#00ff00", font=("monospace",10), justify="left", anchor="nw")
        ov.place(x=5, y=5); return ov
        
    def _tick_overlay(self):
        if not self._overlay or not self._debug: return
        try:
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            weight = self.get_latest_weight(); reader_status = "OK" if self.reader else "ERROR"
            cam_status = "OK" if self.picam2 else "SIMULADA"
            txt = f"Screen: {sw}x{sh}\nWeight: {weight:.2f}g\nReader: {reader_status}\nCamera: {cam_status}"
            self._overlay.config(text=txt)
        except Exception as e: self._overlay.config(text=f"Debug Error: {e}")
        self.root.after(1000, self._tick_overlay)
        
    def _toggle_borderless(self): self._borderless = not self._borderless; self.root.overrideredirect(self._borderless)
    def _toggle_debug(self):
        self._debug = not self._debug
        if self._debug and not self._overlay: self._overlay = self._build_overlay(); self._tick_overlay()
        elif not self._debug and self._overlay: self._overlay.destroy(); self._overlay = None
            
    def _on_close(self):
        try:
            if self.picam2: self.picam2.stop()
            if self.reader: self.reader.stop()
            self.root.quit(); self.root.destroy()
        except Exception as e: print(f"[APP] Error cierre: {e}")
        finally: import sys; sys.exit(0)

    # ===== API para pantallas =====
    def get_cfg(self) -> dict: return self.cfg
    def save_cfg(self) -> None:
        try: save_config(self.cfg)
        except Exception as e: print(f"[APP] Error guardando config: {e}")
    
    def get_reader(self): return self.reader
    def get_tare(self): return self.tare
    
    def get_latest_weight(self) -> float: return self.last_weight
    def get_stability(self) -> bool: return self.is_stable
    def get_raw_weight(self) -> float:
        # Devuelve el peso directo del backend, sin tara/calibración de TareManager
        return self.reader.get_weight() if self.reader else 0.0

    # ===== API de Cámara =====
    def start_camera_preview(self):
        if self.picam2:
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            self.picam2.start_preview(Preview.DRM, x=0, y=0, width=sw, height=sh)

    def stop_camera_preview(self):
        if self.picam2: self.picam2.stop_preview()

    def capture_image(self) -> str:
        path = f"/tmp/capture_{int(time.time())}.jpg"
        if self.picam2:
            try:
                capture_config = self.picam2.create_still_configuration()
                self.picam2.switch_mode_and_capture_file(capture_config, path)
                print(f"[APP] Imagen capturada en {path}")
                return path
            except Exception as e: print(f"[APP] Error al capturar imagen: {e}")
        
        with open(path, "wb") as f: f.write(b"")
        return path

    # ===== Stubs y Conexiones =====
    def request_nutrition(self, image_path: str, grams: float) -> dict:
        # ... (se mantiene igual)
        name = random.choice(["Manzana","Plátano","Desconocido"])
        factors = {"Manzana": {"kcal_g":0.52, "carbs_g":0.14, "protein_g":0.003, "fat_g":0.002},"Plátano": {"kcal_g":0.89, "carbs_g":0.23, "protein_g":0.011, "fat_g":0.003},"Desconocido": {"kcal_g":0.80, "carbs_g":0.15, "protein_g":0.010, "fat_g":0.010}}
        f = factors[name]; g = max(0.0, grams or 0.0)
        return {"name": name, "grams": g, "kcal": g*f["kcal_g"], "carbs": g*f["carbs_g"], "protein": g*f["protein_g"], "fat": g*f["fat_g"], "image_path": image_path}

    def wifi_connect(self, ssid: str, psk: str) -> bool: return False
    def wifi_scan(self): return ["Intek_5G","Intek_2G","Casa_Dani","Invitados"]

    def run(self) -> None:
        try: self.root.mainloop()
        except KeyboardInterrupt: self._on_close()
        finally: self._on_close()

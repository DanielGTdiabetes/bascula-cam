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

try:
    from bascula.services.wifi_config import WifiConfigServer, WifiConfig, auto_connect_on_boot
except Exception as e:
    WifiConfigServer = None
    WifiConfig = None
    auto_connect_on_boot = None
    logging.warning(f"Módulo WiFi no disponible: {e}")

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
        self.wifi_server = None

        t = threading.Thread(target=self._init_services_bg, daemon=True)
        t.start()

    def _init_services_bg(self):
        try:
            # Cargar configuración WiFi y conectar automáticamente
            if auto_connect_on_boot:
                self.splash.set_status("Conectando WiFi...")
                auto_connect_on_boot()
            
            self.splash.set_status("Cargando configuración")
            self.cfg = self._load_full_config()
            
            self.splash.set_status("Iniciando báscula")
            self.reader = SerialReader(port=self.cfg.get("port", "/dev/serial0"), 
                                      baud=self.cfg.get("baud", 115200))
            self.reader.start()
            
            self.splash.set_status("Aplicando tara y suavizado")
            self.tare = TareManager(calib_factor=self.cfg.get("calib_factor", 1.0))
            self.smoother = MovingAverage(size=self.cfg.get("smoothing", 5))

            if CameraService is not None:
                self.splash.set_status("Abriendo cámara")
                try:
                    self.camera = CameraService(width=800, height=480, fps=15)
                    status = getattr(self.camera, "explain_status", lambda: "N/D")()
                    log.info("Estado de la cámara: %s", status)
                except Exception as e:
                    log.error("Fallo CRÍTICO al inicializar la cámara: %s", e)

            if hasattr(self, "camera") and self.camera and hasattr(self.camera, "picam") and self.camera.picam:
                try:
                    self.photo_manager = PhotoManager(logger=log)
                    self.photo_manager.attach_camera(self.camera.picam)
                    log.info("PhotoManager adjuntado a la cámara.")
                except Exception as e:
                    log.warning("No se pudo adjuntar PhotoManager: %s", e)

            # Inicializar servidor WiFi si está disponible
            if WifiConfigServer:
                self.wifi_server = WifiConfigServer(port=8080)

            time.sleep(0.35)
        finally:
            self.root.after(0, self._on_services_ready)

    def _load_full_config(self):
        """Cargar configuración completa (báscula + WiFi)"""
        # Cargar config de báscula
        cfg = load_config()
        
        # Añadir config WiFi si está disponible
        if WifiConfig:
            wifi_cfg = WifiConfig.load_config()
            cfg.update(wifi_cfg)
        
        return cfg

    def _save_full_config(self):
        """Guardar configuración completa"""
        # Guardar config de báscula
        save_config(self.cfg)
        
        # Guardar config WiFi si está disponible
        if WifiConfig:
            wifi_cfg = {k: v for k, v in self.cfg.items() 
                       if k in ['ssid', 'password', 'openai_api_key']}
            if wifi_cfg:
                WifiConfig.save_config(wifi_cfg)

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
        try:
            if self.wifi_server and getattr(self.wifi_server, 'running', False):
                self.wifi_server.stop()
        except Exception:
            pass
        try:
            if self.camera and hasattr(self.camera, "stop"):
                self.camera.stop()
        except Exception:
            pass
        try:
            if self.reader:
                self.reader.stop()
        except Exception:
            pass
        try:
            self.root.quit()
            self.root.destroy()
        finally:
            sys.exit(0)

    def get_cfg(self): 
        return self.cfg
    
    def save_cfg(self): 
        self._save_full_config()
    
    def get_reader(self): 
        return self.reader
    
    def get_tare(self): 
        return self.tare

    def get_latest_weight(self):
        raw = self.reader.get_latest() if self.reader else None
        if raw is not None:
            smoothed = self.smoother.add(raw)
            self._last_weight_net = self.tare.compute_net(smoothed)
        return self._last_weight_net

    def capture_image(self, label: str = "add_item"):
        if not self.camera or not getattr(self.camera, "available", lambda: False)():
            raise RuntimeError("Cámara no operativa para capturar.")
        return self.camera.capture_still()

    def delete_image(self, path: str):
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception as e:
            log.warning(f"No se pudo borrar imagen temporal: {e}")

    def start_wifi_config_server(self):
        """Iniciar servidor de configuración WiFi"""
        if not self.wifi_server:
            log.warning("Servidor WiFi no disponible")
            return False
        
        if self.wifi_server.running:
            log.info("El servidor ya está en ejecución")
            return True
        
        success = self.wifi_server.start()
        if success:
            log.info("Servidor de configuración WiFi iniciado")
            
            # Mostrar información en un diálogo
            dialog = tk.Toplevel(self.root)
            dialog.title("Configuración WiFi")
            dialog.configure(bg="#0a0e1a")
            dialog.geometry("500x300")
            dialog.transient(self.root)
            
            tk.Label(dialog, 
                    text="Servidor de Configuración Activo",
                    bg="#0a0e1a", fg="#00d4aa",
                    font=("DejaVu Sans", 16, "bold")).pack(pady=20)
            
            info_text = """
1. Conéctate a la red WiFi: 'Bascula-Setup'
2. Abre el navegador y ve a:
   http://192.168.4.1:8080
3. Configura tu WiFi y API Key
"""
            tk.Label(dialog, text=info_text,
                    bg="#0a0e1a", fg="#f0f4f8",
                    font=("DejaVu Sans", 12),
                    justify="left").pack(pady=10)
            
            def close_server():
                self.wifi_server.stop()
                dialog.destroy()
            
            tk.Button(dialog, text="Detener Servidor",
                     command=close_server,
                     bg="#ff6b6b", fg="white",
                     font=("DejaVu Sans", 12, "bold")).pack(pady=20)
            
            return True
        else:
            log.error("No se pudo iniciar el servidor")
            return False

    def request_nutrition(self, image_path: str, weight: float):
        """Solicitar información nutricional usando API de OpenAI"""
        api_key = self.cfg.get("openai_api_key", "")
        
        if not api_key:
            log.warning("API Key no configurada, usando datos de prueba")
            time.sleep(1.0)
            return {
                "name": "Alimento de prueba", 
                "grams": weight, 
                "kcal": round(weight * 1.2, 1),
                "carbs": round(weight * 0.15, 1), 
                "protein": round(weight * 0.05, 1),
                "fat": round(weight * 0.03, 1)
            }
        
        # Aquí implementarías la llamada real a OpenAI Vision API
        # Por ahora simulamos con datos más realistas
        log.info(f"Analizando imagen {image_path} con peso {weight:.2f}g")
        
        # TODO: Implementar llamada real a OpenAI
        # import openai
        # openai.api_key = api_key
        # response = openai.Image.create_variation(...)
        
        # Simulación mejorada
        time.sleep(1.5)
        food_samples = [
            {"name": "Manzana", "kcal_per_100": 52, "carbs": 14, "protein": 0.3, "fat": 0.2},
            {"name": "Plátano", "kcal_per_100": 89, "carbs": 23, "protein": 1.1, "fat": 0.3},
            {"name": "Naranja", "kcal_per_100": 47, "carbs": 12, "protein": 0.9, "fat": 0.1},
            {"name": "Pollo", "kcal_per_100": 165, "carbs": 0, "protein": 31, "fat": 3.6},
            {"name": "Arroz", "kcal_per_100": 130, "carbs": 28, "protein": 2.7, "fat": 0.3},
        ]
        
        import random
        sample = random.choice(food_samples)
        factor = weight / 100.0
        
        return {
            "name": sample["name"],
            "grams": weight,
            "kcal": round(sample["kcal_per_100"] * factor, 1),
            "carbs": round(sample["carbs"] * factor, 1),
            "protein": round(sample["protein"] * factor, 1),
            "fat": round(sample["fat"] * factor, 1)
        }

    def run(self):
        self.root.mainloop()
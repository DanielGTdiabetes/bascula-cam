#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aplicación principal de Báscula Digital Pro con UI en Tkinter.
Versión ultra-limpia con diagnósticos mejorados.
"""
import os
import sys
import time
import threading
import logging
from pathlib import Path
import tkinter as tk

log = logging.getLogger(__name__)

# === IMPORTS BÁSICOS ===
try:
    from bascula import utils
    from bascula.ui.splash import SplashScreen
    from bascula.ui.screens import HomeScreen, CalibScreen
    from bascula.ui.screens_wifi import WifiScreen
    from bascula.ui.screens_apikey import ApiKeyScreen
    from bascula.ui.screens_nightscout import NightscoutScreen
    from bascula.ui.screens_diabetes import DiabetesSettingsScreen
    from bascula.ui.screens_tabs_ext import TabbedSettingsMenuScreen
    from bascula.services.camera import CameraService
    from bascula.services.audio import AudioService
    from bascula.services.photo_manager import PhotoManager
    from bascula.services.vision import VisionService
    from bascula.services.logging import setup_logging
    from bascula.services.wakeword import PorcupineWakeWord
    from bascula.services.offqueue import retry_all as offqueue_retry
    from bascula.services.voice import VoiceService
    from bascula.state import AppState
    log.info("Imports básicos OK")
except ImportError as e:
    print(f"Error importando módulos UI: {e}")
    import logging
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger(__name__)

# === BACKEND SERIE ===
ScaleService = None
TareManager = None
BACKEND_AVAILABLE = False

log.info("Buscando ScaleService...")

try:
    from python_backend.bascula.services.scale import ScaleService as RealScaleService
    ScaleService = RealScaleService
    log.info("ScaleService desde python_backend (HARDWARE REAL)")
    BACKEND_AVAILABLE = True
except ImportError as e:
    log.warning(f"python_backend no disponible: {e}")

if not ScaleService:
    try:
        from bascula.services.scale import ScaleService as LocalScaleService
        ScaleService = LocalScaleService
        log.info("ScaleService desde bascula.services (HARDWARE REAL)")
        BACKEND_AVAILABLE = True
    except ImportError as e:
        log.warning(f"bascula.services.scale no disponible: {e}")

if not ScaleService:
    log.error("ScaleService NO ENCONTRADO - usando fallback")
    
    class ScaleService:
        def __init__(self, port=None, baud=115200, logger=None, **kwargs):
            self.port = port or '/dev/ttyAMA0'
            self.baud = baud or 115200
            self.logger = logger or log
            self.weight = 0.0
            self.stable = False
            self.logger.error(f"FALLBACK ScaleService en {self.port}@{self.baud}")
        
        def start(self):
            self.logger.error("FALLBACK iniciado - NO HAY HARDWARE REAL")
            return True
        
        def stop(self):
            pass
        
        def get_latest(self):
            return self.weight
        
        def get_weight(self):
            return self.weight
        
        def is_stable(self):
            return self.stable
        
        def tare(self):
            return True
        
        def calibrate(self, weight):
            return True
        
        def subscribe(self, callback):
            pass

try:
    from bascula.services.tare_manager import TareManager as RealTareManager
    TareManager = RealTareManager
    log.info("TareManager encontrado")
except ImportError as e:
    log.warning(f"TareManager no disponible: {e}")
    
    class TareManager:
        def __init__(self, calib_factor=1.0, **kwargs):
            self.calib_factor = float(calib_factor) if calib_factor else 1.0
            self.offset = 0.0
            log.info(f"TareManager básico (calib_factor={self.calib_factor})")
        
        def apply(self, value):
            if value is None:
                return 0.0
            try:
                result = (float(value) - self.offset) / self.calib_factor
                return max(0.0, result)
            except (ValueError, TypeError, ZeroDivisionError):
                return 0.0
        
        def compute_net(self, value):
            return self.apply(value)
        
        def set_tare(self, value):
            try:
                self.offset = float(value) if value is not None else 0.0
            except (ValueError, TypeError):
                self.offset = 0.0
        
        def update_calib(self, factor):
            try:
                self.calib_factor = float(factor) if factor and factor > 0 else 1.0
            except (ValueError, TypeError):
                self.calib_factor = 1.0


class BasculaAppTk:
    def __init__(self, root=None):
        self.root = root or tk.Tk()
        self.root.withdraw()
        
        try:
            self.root.tk.call('tk', 'scaling', 1.0)
        except Exception:
            pass
        
        self.root.title("Báscula Digital Pro")
        self.root.configure(bg="#0a0e1a")
        
        self.is_rpi = self._detect_rpi()
        
        if self.is_rpi:
            try:
                self.root.attributes("-fullscreen", False)
                res = os.environ.get("BASCULA_UI_RES", "1024x600")
                if "+" not in res:
                    res = res + "+0+0"
                self.root.geometry(res)
                self.root.config(cursor="none")
            except Exception:
                pass
        else:
            self.root.geometry("1024x600")
        
        self.reader = None
        self.tare = None
        self.camera = None
        self.audio = None
        self.photo_manager = None
        self.vision_service = None
        self.wakeword = None
        self.voice = None
        self.state = AppState()
        self.screens = {}
        self.current_screen = None
        
        try:
            self._cfg = utils.load_config()
            if self._cfg is None:
                self._cfg = {}
        except Exception as e:
            log.error(f"Error cargando config: {e}")
            self._cfg = {}
        
        try:
            self.initialize_theme()
        except Exception as e:
            log.warning(f"Error tema: {e}")
        
        self.splash = None
        try:
            self.splash = SplashScreen(
                self.root, 
                title="Báscula Digital Pro", 
                subtitle="Iniciando servicios..."
            )
            self.splash.update()
        except Exception as e:
            log.warning(f"Error splash: {e}")
        
        self._init_services_bg()
        
        try:
            threading.Thread(target=self._startup_maintenance, daemon=True).start()
        except Exception:
            pass
    
    def initialize_theme(self):
        try:
            from bascula.config.themes import apply_theme, update_color_constants, get_theme_manager
            theme_name = self._cfg.get('ui_theme', 'dark_modern')
            apply_theme(self.root, theme_name)
            update_color_constants()
            tm = get_theme_manager()
            if self._cfg.get('theme_scanlines', False):
                tm._apply_scanlines(self.root)
            log.info(f"Tema '{theme_name}' aplicado")
        except Exception as e:
            log.warning(f"Error tema: {e}")

    def _detect_rpi(self):
        try:
            with open("/proc/device-tree/model", "r") as f:
                if "raspberry" in f.read().lower():
                    return True
        except:
            pass
        return os.path.exists("/boot/config.txt") or os.path.exists("/boot/firmware/config.txt")
    
    def get_cfg(self):
        return self._cfg or {}
    
    def save_cfg(self):
        try:
            utils.save_config(self._cfg)
            log.info("Config guardada")
        except Exception as e:
            log.error(f"Error guardando config: {e}")
    
    def get_reader(self):
        return self.reader
    
    def get_tare(self):
        return self.tare
    
    def get_audio(self):
        return self.audio
    
    def get_voice(self):
        return self.voice
    
    def get_latest_weight(self):
        try:
            if not self.reader:
                log.debug("reader es None")
                return 0.0
            
            raw_value = None
            try:
                if hasattr(self.reader, 'get_latest'):
                    raw_value = self.reader.get_latest()
                    log.debug(f"get_latest() = {raw_value}")
                elif hasattr(self.reader, 'get_weight'):
                    raw_value = self.reader.get_weight()
                    log.debug(f"get_weight() = {raw_value}")
                else:
                    log.error(f"Reader {type(self.reader)} sin métodos conocidos")
                    return 0.0
            except Exception as e:
                log.error(f"Error obteniendo raw_value: {e}")
                return 0.0

            if raw_value is None:
                log.debug("raw_value es None")
                return 0.0
            
            try:
                raw_weight = float(raw_value)
                if raw_weight != raw_weight:
                    log.warning("raw_value es NaN")
                    return 0.0
            except (ValueError, TypeError) as e:
                log.error(f"Error convirtiendo {raw_value}: {e}")
                return 0.0
            
            log.debug(f"raw_weight: {raw_weight}g")
            
            if not self.tare:
                log.debug("Sin TareManager")
                return max(0.0, raw_weight)
            
            try:
                if hasattr(self.tare, 'compute_net'):
                    net_weight = self.tare.compute_net(raw_weight)
                    log.debug(f"compute_net({raw_weight}) = {net_weight}")
                elif hasattr(self.tare, 'apply'):
                    net_weight = self.tare.apply(raw_weight)
                    log.debug(f"apply({raw_weight}) = {net_weight}")
                else:
                    log.warning("TareManager sin métodos")
                    return max(0.0, raw_weight)
                
                if net_weight is None:
                    log.warning("TareManager devolvió None")
                    return max(0.0, raw_weight)
                
                try:
                    final_weight = float(net_weight)
                    if final_weight != final_weight:
                        log.warning("TareManager devolvió NaN")
                        return max(0.0, raw_weight)
                    
                    final_weight = max(0.0, final_weight)
                    log.debug(f"peso final: {final_weight}g")
                    return final_weight
                    
                except (ValueError, TypeError) as e:
                    log.error(f"Error convirtiendo net_weight {net_weight}: {e}")
                    return max(0.0, raw_weight)
                    
            except Exception as e:
                log.error(f"Error aplicando tara: {e}")
                return max(0.0, raw_weight)
            
        except Exception as e:
            log.error(f"Error crítico get_latest_weight: {e}")
            return 0.0
    
    def ensure_camera(self):
        if self.camera and self.camera.available():
            return True
        
        try:
            self.camera = CameraService()
            if self.camera.available():
                if self.photo_manager and self.camera.picam:
                    self.photo_manager.attach_camera(self.camera.picam)
                return True
        except Exception as e:
            log.error(f"Error cámara: {e}")
        
        return False
    
    def capture_image(self):
        if not self.ensure_camera():
            raise RuntimeError("Cámara no disponible")
        
        if self.photo_manager:
            path = self.photo_manager.capture(label="weight_capture")
            return str(path)
        else:
            path = self.camera.capture_still()
            return path
    
    def delete_image(self, path):
        try:
            if self.photo_manager:
                self.photo_manager.mark_used(Path(path))
            else:
                Path(path).unlink(missing_ok=True)
        except Exception as e:
            log.warning(f"Error eliminando imagen: {e}")
    
    def request_nutrition(self, image_path, weight):
        import random
        return {
            'name': f'Alimento {random.randint(1,100)}',
            'grams': weight,
            'kcal': random.randint(50, 300),
            'carbs': random.uniform(5, 50),
            'protein': random.uniform(5, 30),
            'fat': random.uniform(1, 20)
        }
    
    def show_screen(self, name):
        prev = self.current_screen
        try:
            if name not in self.screens:
                try:
                    self._create_screen(name)
                except Exception as ce:
                    log.error(f"Error creando pantalla {name}: {ce}")
                    return

            new_screen = self.screens.get(name)
            if not new_screen:
                log.warning(f"Pantalla no disponible: {name}")
                return

            if prev:
                try:
                    if hasattr(prev, 'on_hide'):
                        prev.on_hide()
                    prev.pack_forget()
                except Exception:
                    pass

            self.current_screen = new_screen
            new_screen.pack(fill="both", expand=True)
            try:
                if hasattr(new_screen, 'on_show'):
                    new_screen.on_show()
            except Exception:
                pass
            log.info(f"Pantalla: {name}")
        except Exception as e:
            log.error(f"Error pantalla {name}: {e}")
    
    def _create_screen(self, name):
        try:
            if name == 'home':
                focus = self._cfg.get('focus_mode', True) if self._cfg else True
                if focus:
                    from bascula.ui.focus_screen import FocusScreen
                    self.screens[name] = FocusScreen(self.root, self)
                else:
                    self.screens[name] = HomeScreen(
                        self.root, self,
                        on_open_settings_menu=lambda: self.show_screen('settingsmenu')
                    )
            elif name == 'calib':
                self.screens[name] = CalibScreen(self.root, self)
            elif name == 'settingsmenu':
                self.screens[name] = TabbedSettingsMenuScreen(self.root, self)
            elif name == 'wifi':
                self.screens[name] = WifiScreen(self.root, self)
            elif name == 'apikey':
                self.screens[name] = ApiKeyScreen(self.root, self)
            elif name == 'nightscout':
                self.screens[name] = NightscoutScreen(self.root, self)
            elif name == 'diabetes':
                self.screens[name] = DiabetesSettingsScreen(self.root, self)
            else:
                log.warning(f"Pantalla desconocida: {name}")
        except Exception as e:
            log.error(f"Error creando {name}: {e}")
    
    def _init_services_bg(self):
        t = threading.Thread(target=self._init_services_worker, daemon=True)
        t.start()
    
    def _init_services_worker(self):
        try:
            if self.splash:
                self.root.after(0, lambda: self.splash.set_status("Puerto serie..."))
            
            log.info("=== INICIANDO SERVICIOS ===")
            
            try:
                serial_cfg = self._cfg.get('serial', {}) if self._cfg else {}
                port_candidates = [
                    os.getenv('SERIAL_DEV'),
                    serial_cfg.get('device'),
                    self._cfg.get('port') if self._cfg else None,
                    '/dev/ttyAMA0',
                    '/dev/serial0'
                ]
                
                port = None
                for candidate in port_candidates:
                    if candidate and os.path.exists(candidate):
                        port = candidate
                        log.info(f"Puerto: {port}")
                        break
                
                if not port:
                    port = '/dev/ttyAMA0'
                    log.warning(f"Puerto por defecto: {port}")
                
                baud_candidates = [
                    os.getenv('SERIAL_BAUD'),
                    serial_cfg.get('baudrate'),
                    self._cfg.get('baud') if self._cfg else None,
                    115200
                ]
                
                baud = 115200
                for candidate in baud_candidates:
                    if candidate:
                        try:
                            baud = int(candidate)
                            break
                        except (ValueError, TypeError):
                            continue
                
                calib_factor = 1.0
                if self._cfg:
                    try:
                        calib_factor = float(self._cfg.get('calib_factor', 1.0))
                    except (ValueError, TypeError):
                        calib_factor = 1.0
                
                log.info(f"Config: puerto={port}, baud={baud}, calib={calib_factor}")
                
                try:
                    self.tare = TareManager(calib_factor=calib_factor)
                    log.info("TareManager OK")
                except Exception as e:
                    log.error(f"Error TareManager: {e}")
                    self.tare = None
                
                try:
                    log.info(f"Creando {ScaleService.__name__}")
                    
                    scale_params = {'port': port, 'baud': baud}
                    
                    import inspect
                    try:
                        sig = inspect.signature(ScaleService.__init__)
                        if 'logger' in sig.parameters:
                            scale_params['logger'] = log
                        if 'fail_fast' in sig.parameters:
                            scale_params['fail_fast'] = False
                    except Exception:
                        pass
                    
                    self.reader = ScaleService(**scale_params)
                    
                    start_result = self.reader.start()
                    log.info(f"start() = {start_result}")
                    
                    if start_result is not False:
                        try:
                            test_weight = self.reader.get_latest() if hasattr(self.reader, 'get_latest') else None
                            log.info(f"TEST PESO: {test_weight}g")
                            if test_weight is None or test_weight == 0.0:
                                log.warning("PESO ES 0 - POSIBLE PROBLEMA")
                            else:
                                log.info("PESO DETECTADO OK")
                        except Exception as e:
                            log.error(f"Test peso: {e}")
                    else:
                        raise RuntimeError("ScaleService no inició")
                        
                except Exception as e:
                    log.error(f"ERROR ScaleService: {e}")
                    self.reader = None
            
            except Exception as e:
                log.error(f"Error config serie: {e}")
                self.reader = None
                self.tare = None
            
            self._init_other_services()
            
            if self.splash:
                self.root.after(0, lambda: self.splash.set_status("Interfaz..."))
            
            time.sleep(0.5)
            self.root.after(0, self._on_services_ready)
            
        except Exception as e:
            log.error(f"Error crítico: {e}")
            self.root.after(0, self._show_error_screen, str(e))
    
    def _init_other_services(self):
        if self.splash:
            self.root.after(0, lambda: self.splash.set_status("Audio..."))
        try:
            self.audio = AudioService(cfg=self._cfg, logger=log)
            self.audio.update_config(self._cfg)
            if self._cfg.get('sound_enabled', True):
                self.audio.play_event('boot_ready')
            log.info("Audio OK")
        except Exception as e:
            log.warning(f"Audio: {e}")

        try:
            if self._cfg.get('wakeword_enabled', False):
                self.wakeword = PorcupineWakeWord()
                self.wakeword.start()
                log.info("Wake word OK")
        except Exception as e:
            log.warning(f"Wake word: {e}")
        
        try:
            self.voice = VoiceService()
            log.info("Voz OK")
        except Exception as e:
            log.warning(f"Voz: {e}")
        
        if self.splash:
            self.root.after(0, lambda: self.splash.set_status("Cámara..."))
        try:
            self.camera = CameraService()
            if self.camera.available():
                log.info("Cámara OK")
            else:
                log.info("Sin cámara")
        except Exception as e:
            log.info(f"Cámara: {e}")
        
        try:
            self.photo_manager = PhotoManager(logger=log)
            if self.camera and self.camera.available() and self.camera.picam:
                self.photo_manager.attach_camera(self.camera.picam)
            
            if not self._cfg.get('keep_photos', False):
                self.photo_manager.clear_all()
            
            log.info("Fotos OK")
        except Exception as e:
            log.warning(f"Fotos: {e}")

        try:
            if self.splash:
                self.root.after(0, lambda: self.splash.set_status("IA..."))
            
            model_path = "/opt/vision-lite/models/food_model.tflite"
            labels_path = "/opt/vision-lite/models/labels.txt"
            
            if os.path.exists(model_path) and os.path.exists(labels_path):
                thr = float(self._cfg.get('vision_confidence_threshold', 0.85))
                self.vision_service = VisionService(model_path, labels_path, confidence_threshold=thr)
                log.info("IA OK")
            else:
                log.info("Sin IA")
        except Exception as e:
            log.warning(f"IA: {e}")
        
        try:
            from bascula.domain.foods import load_foods
            self.foods = load_foods()
        except Exception:
            self.foods = []
    
    def _on_services_ready(self):
        try:
            if self.splash:
                self.splash.close()
                self.splash = None
            
            self.show_screen('home')

            services_status = {
                'reader': f'OK ({type(self.reader).__name__})' if self.reader else 'NO',
                'tare': f'OK ({type(self.tare).__name__})' if self.tare else 'NO', 
                'camera': 'OK' if (self.camera and self.camera.available()) else 'NO',
                'audio': 'OK' if self.audio else 'NO',
                'voice': 'OK' if self.voice else 'NO',
                'backend_real': 'SI' if BACKEND_AVAILABLE else 'NO'
            }
            log.info("=== ESTADO SERVICIOS ===")
            for servicio, estado in services_status.items():
                log.info(f"{servicio}: {estado}")
            
            if self.reader:
                try:
                    peso_final = self.get_latest_weight()
                    log.info(f"=== PESO FINAL: {peso_final}g ===")
                    if peso_final == 0.0:
                        log.error("PESO ES 0 - REVISAR HARDWARE")
                except Exception as e:
                    log.error(f"Error test final: {e}")
            
            self.root.deiconify()
            try:
                if self.is_rpi:
                    res = os.environ.get("BASCULA_UI_RES", "1024x600")
                    if "+" not in res:
                        res = res + "+0+0"
                    self.root.geometry(res)
            except Exception:
                pass
            self.root.focus_force()
            
            log.info("APLICACIÓN LISTA")
            
            self._start_heartbeat()
            
            try:
                (Path.home() / ".bascula_boot_ok").touch()
            except:
                pass
            
        except Exception as e:
            log.error(f"Error UI: {e}")
            self._show_error_screen(str(e))

    def _startup_maintenance(self):
        try:
            from bascula.services.retention import prune_jsonl
            base = Path.home() / '.config' / 'bascula'
            targets = [
                (base / 'recipes.jsonl', 365, 1000, 20*1024*1024),
                (base / 'meals.jsonl', 730, 10000, 100*1024*1024),
                (base / 'offqueue.jsonl', 365, 10000, 50*1024*1024),
            ]
            for path, days, entries, bytes_ in targets:
                try:
                    prune_jsonl(path, max_days=days, max_entries=entries, max_bytes=bytes_)
                except Exception:
                    pass
        except Exception:
            pass
    
    def _show_error_screen(self, error_msg):
        if self.splash:
            self.splash.close()
            self.splash = None
        
        self.root.deiconify()
        
        for widget in self.root.winfo_children():
            widget.destroy()
        
        frame = tk.Frame(self.root, bg="#0a0e1a")
        frame.pack(fill="both", expand=True)
        
        tk.Label(
            frame, 
            text="Error de Inicialización", 
            fg="#ff6b6b", 
            bg="#0a0e1a",
            font=("DejaVu Sans", 24, "bold")
        ).pack(pady=50)
        
        tk.Label(
            frame, 
            text=error_msg, 
            fg="#f0f4f8", 
            bg="#0a0e1a",
            font=("DejaVu Sans", 14),
            wraplength=600
        ).pack(pady=20)
        
        tk.Button(
            frame, 
            text="Reintentar",
            command=self._retry_init,
            bg="#00d4aa", 
            fg="white",
            font=("DejaVu Sans", 16),
            bd=0, 
            relief="flat",
            padx=20, 
            pady=10
        ).pack(pady=20)
        
        tk.Button(
            frame, 
            text="Salir",
            command=self.root.quit,
            bg="#ff6b6b", 
            fg="white",
            font=("DejaVu Sans", 16),
            bd=0, 
            relief="flat",
            padx=20, 
            pady=10
        ).pack()
    
    def _retry_init(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        self.root.withdraw()
        self._init_services_bg()
    
    def _start_heartbeat(self):
        def heartbeat():
            p = Path("/run/bascula.alive")
            while True:
                try:
                    p.touch()
                except Exception as e:
                    log.warning(f"Heartbeat failed: {e}")
                time.sleep(

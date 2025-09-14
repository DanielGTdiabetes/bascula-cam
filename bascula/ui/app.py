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
    
    log = logging.getLogger(__name__)
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

# Mocks para fallback
class MockScaleService:
    def __init__(self, port=None, baud=115200, logger=None, **kwargs):
        self.port = port or '/dev/ttyAMA0'
        self.baud = baud or 115200
        self.logger = logger or log
        self.weight = 0.0
        self.stable = False
        self.logger.warning(f"FALLBACK ScaleService en {self.port}@{self.baud}")
    def start(self):
        self.logger.warning("FALLBACK iniciado - NO HAY HARDWARE REAL")
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

class MockTareManager:
    def __init__(self, calib_factor=1.0, **kwargs):
        self.calib_factor = float(calib_factor) if calib_factor else 1.0
        self.offset = 0.0
        log.warning(f"TareManager básico (calib_factor={self.calib_factor})")
    def apply(self, value):
        if value is None: return 0.0
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

try:
    from bascula.services.scale import ScaleService as RealScaleService
    ScaleService = RealScaleService
    log.info("ScaleService REAL OK")
    BACKEND_AVAILABLE = True
except ImportError as e:
    log.error(f"ScaleService REAL no disponible: {e}. Usando mock.")

if not ScaleService:
    ScaleService = MockScaleService

try:
    from bascula.services.tare_manager import TareManager as RealTareManager
    TareManager = RealTareManager
    log.info("TareManager REAL OK")
except ImportError as e:
    log.error(f"TareManager REAL no disponible: {e}. Usando mock.")
    TareManager = MockTareManager


class BasculaAppTk:
    def __init__(self, root=None):
        self.root = root or tk.Tk()
        self.root.withdraw()
        self.logger = logging.getLogger("bascula.ui")
        self.log = self.logger
        
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
        """Worker para inicializar servicios."""
        try:
            # Actualizar splash
            if self.splash:
                self.root.after(0, lambda: self.splash.set_status("Iniciando puerto serie..."))
            
            # Inicializar lector serie y tara (usar claves correctas + env overrides)
            try:
                serial_cfg = (self._cfg.get('serial') or {})
                port = os.getenv('SERIAL_DEV') or serial_cfg.get('device') or self._cfg.get('port', '/dev/serial0')
                baud = int(os.getenv('SERIAL_BAUD') or serial_cfg.get('baudrate') or self._cfg.get('baud', 115200))
                calib_factor = float(self._cfg.get('calib_factor', 1.0))
                
                # Inicializar TareManager primero
                self.tare = TareManager(calib_factor=calib_factor)
                
                # ScaleService usa python_backend/serial_scale si existe; si no, modo nulo
                self.reader = ScaleService(port=port, baud=baud, logger=log, fail_fast=False)
                self.reader.start()

                log.info(f"Báscula inicializada en {port} @ {baud} (calib_factor={calib_factor})")
            except Exception as e:
                log.warning(f"Báscula no disponible: {e}")
                # Fallback a mocks para desarrollo si falla
                calib_factor = self._cfg.get('calib_factor', 1.0)
                self.reader = MockScaleService()
                self.tare = MockTareManager(calib_factor=calib_factor)
            
            # Actualizar splash
            if self.splash:
                self.root.after(0, lambda: self.splash.set_status("Configurando audio..."))
            
            # Inicializar audio
            try:
                self.audio = AudioService(cfg=self._cfg, logger=log)
                self.audio.update_config(self._cfg)
                if self._cfg.get('sound_enabled', True):
                    self.audio.play_event('boot_ready')
                log.info("Audio inicializado")
            except Exception as e:
                log.warning(f"Audio no disponible: {e}")

            # Wake word (optional, non-blocking)
            try:
                if bool(self._cfg.get('wakeword_enabled', False)):
                    self.wakeword = PorcupineWakeWord()
                    self.wakeword.start()
                    log.info("Wake word activada")
            except Exception as e:
                log.warning(f"Wake word no disponible: {e}")
            
            # Servicio de voz (ASR/TTS local) disponible globalmente
            try:
                self.voice = VoiceService()
                log.info("Servicio de voz listo")
            except Exception as e:
                log.warning(f"Voz no disponible: {e}")
            
            # Actualizar splash
            if self.splash:
                self.root.after(0, lambda: self.splash.set_status("Preparando cámara..."))
            
            # Inicializar cámara (opcional)
            try:
                self.camera = CameraService()
                if self.camera.available():
                    log.info("cámara disponible")
                else:
                    log.info("Cámara no detectada")
            except Exception as e:
                log.info(f"Cámara no disponible: {e}")
            
            # Inicializar gestor de fotos
            try:
                self.photo_manager = PhotoManager(logger=log)
                if self.camera and self.camera.available() and self.camera.picam:
                    self.photo_manager.attach_camera(self.camera.picam)
                
                if not self._cfg.get('keep_photos', False):
                    self.photo_manager.clear_all()
                
                log.info("Gestor de fotos inicializado")
            except Exception as e:
                log.warning(f"Gestor de fotos no disponible: {e}")

            # Cargar alimentos locales en memoria (para sugerencias)
            try:
                from bascula.domain.foods import load_foods
                self.foods = load_foods()
            except Exception:
                self.foods = []

            # Inicializar IA de visión (opcional)
            try:
                if self.splash:
                    self.root.after(0, lambda: self.splash.set_status("Cargando IA de Visión..."))
                model_path = "/opt/vision-lite/models/food_model.tflite"
                labels_path = "/opt/vision-lite/models/labels.txt"
                if os.path.exists(model_path) and os.path.exists(labels_path):
                    thr = float(self._cfg.get('vision_confidence_threshold', 0.85))
                    self.vision_service = VisionService(model_path, labels_path, confidence_threshold=thr)
                    log.info("Servicio de Visión (TFLite) cargado")
                else:
                    log.info("Modelo TFLite no encontrado; visión desactivada")
            except Exception as e:
                log.warning(f"Visión no disponible: {e}")
            
            # Actualizar splash
            if self.splash:
                self.root.after(0, lambda: self.splash.set_status("Cargando interfaz..."))
            
            time.sleep(0.5)
            
            # Construir UI en el hilo principal
            self.root.after(0, self._on_services_ready)

            # Lanzar reintento de cola offline (Nightscout) si hay config
            try:
                ns_file = Path.home() / ".config" / "bascula" / "nightscout.json"
                if ns_file.exists():
                    import json as _json
                    cfg = _json.loads(ns_file.read_text(encoding="utf-8"))
                    url = (cfg.get('url') or '').strip()
                    tok = (cfg.get('token') or '').strip()
                    if url:
                        offqueue_retry(url, tok)
                        # Network watcher to trigger retries on connectivity return
                        def _net_watch():
                            try:
                                import time as _t
                                import requests as rq
                            except Exception:
                                return
                            last_ok = False
                            while True:
                                try:
                                    r = rq.get(f"{url}/api/v1/status.json", timeout=5)
                                    ok = r.ok
                                except rq.exceptions.RequestException:
                                    ok = False
                                if ok and not last_ok:
                                    offqueue_retry(url, tok)
                                last_ok = ok
                                _t.sleep(30)
                        threading.Thread(target=_net_watch, daemon=True).start()
            except Exception:
                pass
            
        except Exception as e:
            log.error(f"Error crítico inicializando servicios: {e}")
            self.root.after(0, self._show_error_screen, str(e))
    
    def _on_services_ready(self):
        """Callback cuando los servicios están listos."""
        try:
            # Cerrar splash
            if self.splash:
                self.splash.close()
                self.splash = None
            
            # Mostrar pantalla principal
            self.show_screen('home')

            # Aviso si la báscula física no está disponible (usa mocks)
            try:
                if isinstance(self.reader, MockSerialReader):
                    self._warn_hw_missing("Báscula no detectada. Revisar cableado/puerto y reiniciar.")
            except Exception:
                pass
            
            # Mostrar ventana
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
            
            log.info("Aplicación lista")
            
            # Log del estado de servicios para depuración
            services_status = {
                'reader': 'OK' if self.reader else 'NO',
                'tare': 'OK' if self.tare else 'NO',
                'camera': 'OK' if (self.camera and self.camera.available()) else 'NO',
                'audio': 'OK' if self.audio else 'NO',
                'voice': 'OK' if self.voice else 'NO',
                'backend_real': 'SI' if BACKEND_AVAILABLE else 'NO'
            }
            log.info(f"Estado servicios: {services_status}")
            
            # Iniciar heartbeat
            self._start_heartbeat()
            
            # Marcar boot completado
            try:
                (Path.home() / ".bascula_boot_ok").touch()
            except:
                pass
            
        except Exception as e:
            log.error(f"Error mostrando UI: {e}")
            self._show_error_screen(str(e))

    def _startup_maintenance(self):
        """Poda de ficheros JSONL para mantener espacio en disco."""
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
    
    def _show_error_screen(self, error_msg: str):
        """Muestra una pantalla de error."""
        if self.splash:
            self.splash.close()
            self.splash = None
        
        self.root.deiconify()
        
        # Limpiar ventana
        for widget in self.root.winfo_children():
            widget.destroy()
        
        # Mostrar error
        frame = tk.Frame(self.root, bg="#0a0e1a")
        frame.pack(fill="both", expand=True)
        
        tk.Label(frame, text="⚠ Error de Inicialización", 
                fg="#ff6b6b", bg="#0a0e1a",
                font=("DejaVu Sans", 24, "bold")).pack(pady=50)
        
        tk.Label(frame, text=error_msg, 
                fg="#f0f4f8", bg="#0a0e1a",
                font=("DejaVu Sans", 14),
                wraplength=600).pack(pady=20)
        
        tk.Button(frame, text="Reintentar",
                 command=self._retry_init,
                 bg="#00d4aa", fg="white",
                 font=("DejaVu Sans", 16),
                 bd=0, relief="flat",
                 padx=20, pady=10).pack(pady=20)
        
        tk.Button(frame, text="Salir",
                 command=self.root.quit,
                 bg="#ff6b6b", fg="white",
                 font=("DejaVu Sans", 16),
                 bd=0, relief="flat",
                 padx=20, pady=10).pack()
    
    def _retry_init(self):
        """Reintenta la inicialización."""
        for widget in self.root.winfo_children():
            widget.destroy()
        self.root.withdraw()
        self._init_services_bg()
    
    def _start_heartbeat(self):
        """Inicia el heartbeat para monitoreo."""
        def heartbeat():
            p = Path("/run/bascula.alive")
            while True:
                try:
                    p.touch()
                except Exception as e:
                    log.warning(f"Heartbeat failed: {e}")
                time.sleep(5)
        
        threading.Thread(target=heartbeat, daemon=True).start()

    def _warn_hw_missing(self, msg: str):
        try:
            top = tk.Toplevel(self.root)
            top.title("Aviso")
            top.configure(bg="#141823")
            try: 
                top.attributes("-topmost", True)
            except Exception: 
                pass
            
            tk.Label(top, text="⚠️  Hardware no disponible", 
                     bg="#141823", fg="#ffa500", 
                     font=("DejaVu Sans", 14, "bold")).pack(padx=14, pady=(10,4))
            
            tk.Label(top, text=msg, 
                     bg="#141823", fg="#f0f4f8", 
                     font=("DejaVu Sans", 12), 
                     wraplength=420, justify="left").pack(padx=14, pady=(0,10))
            
            tk.Button(top, text="Entendido", command=top.destroy, 
                      bg="#6b7280", fg="white", bd=0, relief="flat", 
                      padx=12, pady=6).pack(pady=(0,10))
            
            top.update_idletasks()
            
            # Centrar en pantalla
            x = self.root.winfo_rootx() + (self.root.winfo_width() - top.winfo_width())//2
            y = self.root.winfo_rooty() + (self.root.winfo_height() - top.winfo_height())//3
            top.geometry(f"+{max(0,x)}+{max(0,y)}")
            
            # Autocerrar en 8 segundos
            top.after(8000, lambda: (top.winfo_exists() and top.destroy()))
            
        except Exception:
            pass
    
    def run(self):
        """Ejecuta el loop principal de la aplicación."""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            log.info("Aplicación interrumpida por usuario")
        except Exception as e:
            log.error(f"Error en mainloop: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Limpia recursos al cerrar."""
        try:
            if self.reader and hasattr(self.reader, 'stop'):
                self.reader.stop()
            if self.camera and hasattr(self.camera, 'stop'):
                self.camera.stop()
            log.info("Recursos liberados")
        except Exception as e:
            log.error(f"Error en cleanup: {e}")

def main():
    """Punto de entrada principal."""
    # Configurar logging
    setup_logging(level=logging.INFO)
    
    # Crear y ejecutar aplicación
    try:
        app = BasculaAppTk()
        app.run()
    except Exception as e:
        log.error(f"Error fatal: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()

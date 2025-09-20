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
BACKEND_AVAILABLE = False

log.info("Buscando ScaleService...")


class MockScaleService:
    def __init__(self, device=None, baud=None, logger=None, **kwargs):
        self._logger = logger or log
        self._device = device or "/dev/serial0"
        self._baud = baud or kwargs.get("baudrate") or 115200
        self._weight = 0.0
        self._stable = False
        self._calibration = float(kwargs.get("calibration_factor", 1.0) or 1.0)
        self._logger.warning(
            f"ScaleService mock activo en {self._device}@{self._baud} (sin hardware)"
        )

    def start(self):
        self._logger.warning("ScaleService mock iniciado")

    def stop(self):
        self._logger.warning("ScaleService mock detenido")

    def get_latest(self):
        return float(self._weight)

    def get_weight(self):
        return float(self._weight) * self._calibration

    def is_stable(self):
        return bool(self._stable)

    def tare(self):
        self._weight = 0.0
        return True

    def zero(self):
        self._weight = 0.0
        return True

    def send_command(self, command):
        self._logger.debug(f"MockScaleService send_command: {command}")

    def subscribe(self, callback):
        if callable(callback):
            try:
                callback(self.get_weight(), self.is_stable())
            except Exception:
                pass

    def set_calibration_factor(self, factor):
        try:
            self._calibration = float(factor)
        except Exception:
            self._calibration = 1.0

    def get_calibration_factor(self):
        return float(self._calibration)


try:
    from bascula.services.scale import ScaleService as RealScaleService

    ScaleService = RealScaleService
    log.info("ScaleService REAL OK")
    BACKEND_AVAILABLE = True
except ImportError as e:
    log.error(f"ScaleService REAL no disponible: {e}. Usando mock.")

if not ScaleService:
    ScaleService = MockScaleService

class BasculaAppTk:
    CURSOR_HIDE_TIMEOUT_MS = 3000

    @staticmethod
    def _env_flag(name: str, default=None):
        value = os.getenv(name)
        if value is None:
            return default
        value = value.strip().lower()
        if value in ("1", "true", "yes", "on", "enabled", "enable"):
            return True
        if value in ("0", "false", "no", "off", "disabled", "disable"):
            return False
        return default

    def __init__(self, root=None, kiosk=None, debug=None):
        # Logger principal (disponible incluso si Tk falla)
        self.logger = logging.getLogger("bascula.ui")
        self.logger.setLevel(logging.INFO)

        # Alias de compatibilidad usado en screens.py: self.app.log
        self.log = self.logger

        self.headless = False
        self.root = root
        self._cursor_job = None
        self._cursor_hidden = False
        self._last_motion = time.monotonic()
        self.screen_width = None
        self.screen_height = None
        self.is_rpi = self._detect_rpi()

        env_debug = self._env_flag("BASCULA_DEBUG", default=False)
        if debug is None:
            self.debug_mode = env_debug
        else:
            self.debug_mode = bool(debug)
        if self.debug_mode:
            self.logger.setLevel(logging.DEBUG)

        display_present = bool(os.environ.get("DISPLAY"))
        env_kiosk = self._env_flag("BASCULA_KIOSK", default=None)
        if kiosk is None:
            if env_kiosk is None:
                self.kiosk_mode = display_present
            else:
                self.kiosk_mode = env_kiosk
        else:
            self.kiosk_mode = bool(kiosk)

        if self.root is None:
            try:
                self.root = tk.Tk()
            except tk.TclError as exc:
                self.headless = True
                self.root = None
                self.logger.warning("Tkinter no disponible, modo headless activado: %s", exc)

        if self.root:
            try:
                self.root.tk.call('tk', 'scaling', 1.0)
            except Exception:
                pass

            self.root.withdraw()
            self.root.title("Báscula Digital Pro")
            self.root.configure(bg="#0a0e1a")

            self._apply_window_mode()
            self._setup_cursor_hider()
        else:
            self.kiosk_mode = False
            self.headless = True

        self.reader = None
        self.calibration_factor = 1.0
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
            self.calibration_factor = float(self._cfg.get('calib_factor', 1.0) or 1.0)
        except Exception:
            self.calibration_factor = 1.0
        
        if self.root:
            try:
                self.initialize_theme()
            except Exception as e:
                log.warning(f"Error tema: {e}")

        self.splash = None
        if self.root:
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

    def _apply_window_mode(self):
        if not self.root:
            return

        if self.kiosk_mode:
            try:
                self.root.attributes("-fullscreen", True)
            except Exception:
                pass
            try:
                self.root.wm_attributes("-type", "dock")
            except Exception:
                pass
            try:
                self.root.overrideredirect(True)
            except Exception:
                pass
            self.root.protocol("WM_DELETE_WINDOW", lambda: None)
            self.root.bind_all("<Escape>", lambda e: "break")
            try:
                self.root.update_idletasks()
            except Exception:
                pass
            try:
                width = self.root.winfo_screenwidth()
                height = self.root.winfo_screenheight()
            except Exception:
                width = height = None
            if width and height:
                self.root.geometry(f"{width}x{height}+0+0")
            try:
                self.root.attributes("-topmost", True)
            except Exception:
                pass
        else:
            try:
                self.root.attributes("-fullscreen", False)
            except Exception:
                pass
            try:
                self.root.overrideredirect(False)
            except Exception:
                pass
            try:
                self.root.attributes("-topmost", False)
            except Exception:
                pass
            try:
                self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
            except Exception:
                pass

            if self.is_rpi:
                try:
                    res = os.environ.get("BASCULA_UI_RES", "1024x600")
                    if "+" not in res:
                        res = res + "+0+0"
                    self.root.geometry(res)
                except Exception:
                    pass
            else:
                try:
                    self.root.geometry("1024x600")
                except Exception:
                    pass

        try:
            self.root.update_idletasks()
            self.screen_width = self.root.winfo_screenwidth()
            self.screen_height = self.root.winfo_screenheight()
        except Exception:
            pass

        if self.debug_mode:
            self._bind_debug_shortcut()

    def _bind_debug_shortcut(self):
        if not self.root:
            return
        self.root.bind_all("<Control-Shift-KeyPress-q>", self._debug_exit, add="+")
        self.root.bind_all("<Control-Shift-KeyPress-Q>", self._debug_exit, add="+")

    def _debug_exit(self, event=None):
        if not self.debug_mode:
            return "break"
        self.logger.warning("Atajo de depuración activado: cerrando UI")
        if self.root and self.root.winfo_exists():
            self.root.destroy()
        return "break"

    def _setup_cursor_hider(self):
        if not self.root:
            return
        self._last_motion = time.monotonic()
        self._cursor_hidden = False
        self.root.config(cursor="")
        self.root.bind_all("<Motion>", self._on_pointer_motion, add="+")
        self._cursor_job = self.root.after(250, self._check_cursor_timeout)

    def _on_pointer_motion(self, event=None):
        self._last_motion = time.monotonic()
        if self._cursor_hidden and self.root and self.root.winfo_exists():
            try:
                self.root.config(cursor="")
            except Exception:
                pass
            self._cursor_hidden = False
        if self.root and self._cursor_job:
            try:
                self.root.after_cancel(self._cursor_job)
            except Exception:
                pass
            self._cursor_job = None
        if self.root and self.root.winfo_exists():
            self._cursor_job = self.root.after(250, self._check_cursor_timeout)

    def _check_cursor_timeout(self):
        if not self.root or not self.root.winfo_exists():
            return
        if (time.monotonic() - self._last_motion) * 1000 >= self.CURSOR_HIDE_TIMEOUT_MS:
            if not self._cursor_hidden:
                try:
                    self.root.config(cursor="none")
                except Exception:
                    pass
                self._cursor_hidden = True
        self._cursor_job = self.root.after(250, self._check_cursor_timeout)

    def initialize_theme(self):
        if not self.root:
            return
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

    def get_audio(self):
        return self.audio

    def get_voice(self):
        return self.voice

    def get_latest_weight(self):
        if not self.reader:
            log.debug("reader es None")
            return 0.0
        try:
            if hasattr(self.reader, 'get_weight'):
                value = self.reader.get_weight()
            elif hasattr(self.reader, 'get_latest'):
                value = self.reader.get_latest()
            else:
                log.error(f"Reader {type(self.reader)} sin métodos conocidos")
                return 0.0
            if value is None:
                return 0.0
            weight = float(value)
            if weight != weight:
                return 0.0
            return max(0.0, weight)
        except Exception as e:
            log.error(f"Error obteniendo peso: {e}")
            return 0.0

    def get_calibration_factor(self) -> float:
        try:
            return float(self.calibration_factor)
        except Exception:
            return 1.0

    def set_calibration_factor(self, factor: float, persist: bool = False) -> None:
        try:
            value = float(factor)
            if value <= 0:
                raise ValueError
        except Exception:
            value = 1.0
        self.calibration_factor = value
        if self.reader and hasattr(self.reader, 'set_calibration_factor'):
            try:
                self.reader.set_calibration_factor(value)
            except Exception as exc:
                log.debug(f"No se pudo aplicar calibración en tiempo real: {exc}")
        if persist:
            self._cfg['calib_factor'] = value
            self.save_cfg()

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
        if not self.root:
            log.warning(f"No se puede mostrar la pantalla '{name}' en modo headless")
            return
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
        if not self.root:
            return
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
            if self.splash and self.root:
                self.root.after(0, lambda: self.splash.set_status("Iniciando puerto serie..."))
            
            # Inicializar lector serie (usar claves correctas + env overrides)
            try:
                serial_cfg = (self._cfg.get('serial') or {})
                port = os.getenv('BASCULA_DEVICE') or os.getenv('SERIAL_DEV') or serial_cfg.get('device') or self._cfg.get('port', '/dev/serial0')
                baud = os.getenv('BASCULA_BAUD') or os.getenv('SERIAL_BAUD') or serial_cfg.get('baudrate') or self._cfg.get('baud', 115200)
                try:
                    baud_int = int(baud)
                except Exception:
                    baud_int = None
                self.calibration_factor = float(self._cfg.get('calib_factor', 1.0) or 1.0)

                self.reader = ScaleService(
                    device=port,
                    baud=baud_int,
                    logger=log,
                    fail_fast=False,
                    calibration_factor=self.calibration_factor,
                )
                self.reader.start()
                if hasattr(self.reader, 'set_calibration_factor'):
                    try:
                        self.reader.set_calibration_factor(self.calibration_factor)
                    except Exception as exc:
                        log.debug(f"No se pudo ajustar calibración inicial: {exc}")
                log.info(
                    "Báscula inicializada en %s @ %s (calib_factor=%.4f)",
                    port,
                    baud_int or 'auto',
                    self.calibration_factor,
                )
            except Exception as e:
                log.warning(f"Báscula no disponible: {e}")
                self.reader = MockScaleService(calibration_factor=self.calibration_factor)
            
            # Actualizar splash
            if self.splash and self.root:
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
            if self.splash and self.root:
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
                if self.splash and self.root:
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
            if self.splash and self.root:
                self.root.after(0, lambda: self.splash.set_status("Cargando interfaz..."))
            
            time.sleep(0.5)
            
            # Construir UI en el hilo principal
            if self.root:
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
            if self.root:
                self.root.after(0, self._show_error_screen, str(e))
    
    def _on_services_ready(self):
        """Callback cuando los servicios están listos."""
        try:
            # Cerrar splash
            if self.splash:
                self.splash.close()
                self.splash = None
            
            # Mostrar pantalla principal
            if self.root:
                self.show_screen('home')

            # Aviso si la báscula física no está disponible (usa mocks)
            try:
                if isinstance(self.reader, MockScaleService):
                    self._warn_hw_missing("Báscula no detectada. Revisar cableado/puerto y reiniciar.")
            except Exception:
                pass

            # Mostrar ventana
            if self.root:
                self.root.deiconify()
                try:
                    if self.is_rpi and not self.kiosk_mode:
                        res = os.environ.get("BASCULA_UI_RES", "1024x600")
                        if "+" not in res:
                            res = res + "+0+0"
                        self.root.geometry(res)
                except Exception:
                    pass
                try:
                    self.root.focus_force()
                except Exception:
                    pass

            log.info("Aplicación lista")
            
            # Log del estado de servicios para depuración
            services_status = {
                'reader': 'OK' if self.reader else 'NO',
                'camera': 'OK' if (self.camera and self.camera.available()) else 'NO',
                'audio': 'OK' if self.audio else 'NO',
                'voice': 'OK' if self.voice else 'NO',
                'calibration': f"{self.calibration_factor:.3f}",
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
            if self.root:
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
        if not self.root:
            log.error(f"Error de inicialización sin UI disponible: {error_msg}")
            return
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
        if not self.root:
            return
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
        if not self.root:
            log.warning(f"Hardware faltante: {msg}")
            return
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
        if self.headless or not self.root:
            log.warning("UI Tk no disponible; ejecutando en modo headless.")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                log.info("Aplicación interrumpida por usuario")
            finally:
                self.cleanup()
            return

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
        if self.root and self._cursor_job:
            try:
                self.root.after_cancel(self._cursor_job)
            except Exception:
                pass
            self._cursor_job = None
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

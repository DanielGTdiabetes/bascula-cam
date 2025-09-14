def _init_services_worker(self):
        """Worker para inicializar servicios con diagnóstico detallado."""
        try:
            # Actualizar splash
            if self.splash:
                self.root.after(0, lambda: self.splash.set_status("Iniciando puerto serie..."))
            
            # Inicializar lector serie y tara con diagnóstico detallado
            log.info("=== INICIANDO SERVICIOS SERIE ===")
            
            self._init_scale_services()
            
            # Resto de servicios
            self._init_audio_service()
            self._init_voice_services()
            self._init_camera_service()
            self._init_photo_manager()
            self._init_vision_service()
            
            # Finalizar inicialización
            if self.splash:
                self.root.after(0, lambda: self.splash.set_status("Cargando interfaz..."))
            
            time.sleep(0.5)
            
            # Construir UI en el hilo principal
            self.root.after(0, self._on_services_ready)
            
            # Inicializar cola offline de Nightscout si existe
            self._init_nightscout_queue()
            
        except Exception as e:
            log.error(f"Error crítico inicializando servicios: {e}")
            self.root.after(0, self._show_error_screen, str(e))
    
    def _init_scale_services(self):
        """Inicializa los servicios de báscula."""
        try:
            # Obtener configuración con múltiples fuentes
            serial_cfg = self._cfg.get('serial', {}) if self._cfg else {}
            log.info(f"Config serial desde archivo: {serial_cfg}")
            
            # Determinar puerto con prioridades
            port_candidates = [
                os.getenv('SERIAL_DEV'),
                serial_cfg.get('device'),
                self._cfg.get('port') if self._cfg else None,
                '/dev/ttyAMA0',  # Preferir ttyAMA0 en RPi
                '/dev/serial0'
            ]
            
            port = None
            for candidate in port_candidates:
                if candidate and os.path.exists(candidate):
                    port = candidate
                    log.info(f"Puerto seleccionado: {port}")
                    break
                elif candidate:
                    log.debug(f"Puerto candidato no existe: {candidate}")
            
            if not port:
                port = '/dev/ttyAMA0'  # Fallback final
                log.warning(f"Ningún puerto encontrado, usando fallback: {port}")
            
            # Determinar baudrate
            baud_candidates = [
                os.getenv('SERIAL_BAUD'),
                serial_cfg.get('baudrate'),
                self    def _on_services_ready(self):
        """Callback cuando los servicios están listos."""
        try:
            # Cerrar splash
            if self.splash:
                self.splash.close()
                self.splash = None
            
            # Mostrar pantalla principal
            self.show_screen('home')

            # Avisos de hardware faltante con información detallada
            try:
                if not self.reader:
                    self._warn_hw_missing("Báscula no detectada. Revisar conexión serie y reiniciar.")
                elif not BACKEND_AVAILABLE:
                    self._warn_hw_missing("Hardware de báscula en modo simulación.")
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
            
            # Log detallado del estado de servicios para depuración
            services_status = {
                'reader': f'OK ({type(self.reader).__name__})' if self.reader else 'NO',
                'tare': f'OK ({type(self.tare).__name__})' if self.tare else 'NO', 
                'camera': 'OK' if (self.camera and self.camera.available()) else 'NO',
                'audio': 'OK' if self.audio else 'NO',
                'voice': 'OK' if self.voice else 'NO',
                'backend_real': 'SI' if BACKEND_AVAILABLE else 'NO'
            }
            log.info(f"Estado servicios: {services_status}")
            
            # Test inmediato del peso si hay reader
            if self.reader:
                try:
                    test_weight = self.get_latest_weight()
                    log.info(f"Test peso inicial: {test_weight}g")
                except Exception as e:
                    log.error(f"Error en test peso inicial: {e}")
            
            # Iniciar heartbeat
            self._start_heartbeat()
            
            # Marcar boot completado
            try:
                (Path.home() / ".bascula_boot_ok").touch()
            except:
                pass
            
        except Exception as e:
            log.error(f"Error mostrando UI: {e}")
            self._show_error_screen(str(e))#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aplicación principal de Báscula Digital Pro con UI en Tkinter.
Versión simplificada con manejo robusto de errores.
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
    # Preferir módulos dedicados (shims) y mantener legacy como fallback
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
    from bascula.services.scale import ScaleService
    from bascula.services.tare_manager import TareManager
    from bascula.state import AppState
    
    log = logging.getLogger(__name__)
    log.info("✔ Imports básicos exitosos")
    
except ImportError as e:
    print(f"Error importando módulos UI: {e}")
    import logging
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger(__name__)

log = logging.getLogger(__name__)

class BasculaAppTk:
    def __init__(self, root=None):
        """Inicializa la aplicación con manejo robusto de errores."""
        self.root = root or tk.Tk()
        self.root.withdraw()  # Ocultar mientras carga
        # Asegurar escala Tk razonable en Pi (evita UI en 1/4 de pantalla)
        try:
            self.root.tk.call('tk', 'scaling', 1.0)
        except Exception:
            pass
        
        # Configuración de ventana
        self.root.title("Báscula Digital Pro")
        self.root.configure(bg="#0a0e1a")
        
        # Detectar si estamos en Raspberry Pi
        self.is_rpi = self._detect_rpi()
        
        if self.is_rpi:
            try:
                self.root.attributes("-fullscreen", False)
            except Exception:
                pass
            try:
                res = os.environ.get("BASCULA_UI_RES", "1024x600")
                if "+" not in res:
                    res = res + "+0+0"
                self.root.geometry(res)
                try:
                    w, h = res.split("+", 1)[0].split("x")
                    self.root.minsize(int(w), int(h))
                except Exception:
                    pass
            except Exception:
                pass
            self.root.config(cursor="none")
        else:
            self.root.geometry("1024x600")
        
        # Servicios
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
        
        # Configuración
        self._cfg = utils.load_config()
        
        # Inicializar tema visual antes de crear pantallas
        try:
            self.initialize_theme()
        except Exception as _e:
            try:
                log.warning(f"No se pudo aplicar tema personalizado en inicio: {_e}")
            except Exception:
                pass
        
        # Splash screen
        self.splash = None
        try:
            self.splash = SplashScreen(self.root, title="Báscula Digital Pro", subtitle="Iniciando servicios...")
            self.splash.update()
        except Exception as e:
            log.warning(f"No se pudo crear splash screen: {e}")
        
        # Iniciar servicios en segundo plano
        self._init_services_bg()
        # Mantenimiento ligero en segundo plano (poda de JSONL)
        try:
            import threading as _th
            _th.Thread(target=self._startup_maintenance, daemon=True).start()
        except Exception:
            pass
    
    def initialize_theme(self):
        """Inicializa el tema al arrancar la aplicación"""
        try:
            from bascula.config.themes import apply_theme as tm_apply, update_color_constants, get_theme_manager
            # Cargar tema guardado
            theme_name = self._cfg.get('ui_theme', 'dark_modern')
            # Aplicar tema
            tm_apply(self.root, theme_name)
            update_color_constants()
            # Efectos especiales
            tm = get_theme_manager()
            if self._cfg.get('theme_scanlines', False):
                tm._apply_scanlines(self.root)
            try:
                log.info(f"Tema '{theme_name}' aplicado")
            except Exception:
                pass
        except Exception as e:
            try:
                log.warning(f"No se pudo aplicar tema personalizado: {e}")
            except Exception:
                pass

    def _detect_rpi(self) -> bool:
        """Detecta si estamos ejecutando en Raspberry Pi."""
        try:
            with open("/proc/device-tree/model", "r") as f:
                if "raspberry" in f.read().lower():
                    return True
        except:
            pass
        return os.path.exists("/boot/config.txt") or os.path.exists("/boot/firmware/config.txt")
    
    def get_cfg(self) -> dict:
        """Retorna la configuración actual."""
        return self._cfg
    
    def save_cfg(self) -> None:
        """Guarda la configuración."""
        try:
            utils.save_config(self._cfg)
            log.info("Configuración guardada")
        except Exception as e:
            log.error(f"Error guardando configuración: {e}")
    
    def get_reader(self):
        """Retorna el lector serie."""
        return self.reader
    
    def get_tare(self):
        """Retorna el gestor de tara."""
        return self.tare
    
    def get_audio(self):
        """Retorna el servicio de audio."""
        return self.audio
    
    def get_voice(self):
        """Retorna el servicio de voz (ASR/TTS local)."""
        return self.voice
    
    def get_latest_weight(self) -> float:
        """Obtiene el peso actual con tara aplicada, con logs y fallbacks."""
        try:
            if self.reader and hasattr(self.reader, 'get_latest'):
                raw_value = self.reader.get_latest()
                if raw_value is None:
                    log.debug("get_latest_weight: Lector no devolvió valor.")
                    return 0.0
                
                if self.tare:
                    # Prueba métodos comunes de TareManager
                    if hasattr(self.tare, 'compute_net'):
                        net_weight = self.tare.compute_net(raw_value)
                    elif hasattr(self.tare, 'apply'):
                        net_weight = self.tare.apply(raw_value)
                    else:
                        log.warning("TareManager sin método apply/compute_net; usando raw.")
                        return float(raw_value)
                    
                    log.debug(f"get_latest_weight: raw={raw_value}, net={net_weight}")
                    return net_weight
                
                # Fallback si tare no listo
                return float(raw_value)
        except Exception as e:
            log.error(f"Error obteniendo peso: {e}")
        return 0.0
    
    def ensure_camera(self) -> bool:
        """Asegura que la cámara esté disponible."""
        if self.camera and self.camera.available():
            return True
        
        try:
            self.camera = CameraService()
            if self.camera.available():
                if self.photo_manager and self.camera.picam:
                    self.photo_manager.attach_camera(self.camera.picam)
                return True
        except Exception as e:
            log.error(f"Error inicializando cámara: {e}")
        
        return False
    
    def capture_image(self) -> str:
        """Captura una imagen y retorna la ruta."""
        if not self.ensure_camera():
            raise RuntimeError("Cámara no disponible")
        
        if self.photo_manager:
            path = self.photo_manager.capture(label="weight_capture")
            return str(path)
        else:
            path = self.camera.capture_still()
            return path
    
    def delete_image(self, path: str):
        """Elimina una imagen capturada."""
        try:
            if self.photo_manager:
                self.photo_manager.mark_used(Path(path))
            else:
                Path(path).unlink(missing_ok=True)
        except Exception as e:
            log.warning(f"No se pudo eliminar imagen: {e}")
    
    def request_nutrition(self, image_path: str, weight: float) -> dict:
        """Solicita análisis nutricional (placeholder)."""
        import random
        return {
            'name': f'Alimento {random.randint(1,100)}',
            'grams': weight,
            'kcal': random.randint(50, 300),
            'carbs': random.uniform(5, 50),
            'protein': random.uniform(5, 30),
            'fat': random.uniform(1, 20)
        }
    
    def show_screen(self, name: str):
        """Cambia a la pantalla especificada de forma segura.

        Si la creación de la nueva pantalla falla, mantiene la pantalla
        actual visible y registra el error para evitar dejar la UI en negro.
        """
        prev = self.current_screen
        try:
            # Asegurar instancia creada antes de ocultar la actual
            if name not in self.screens:
                try:
                    self._create_screen(name)
                except Exception as ce:
                    log.error(f"Error creando pantalla {name}: {ce}")
                    return  # Mantener pantalla previa

            new_screen = self.screens.get(name)
            if not new_screen:
                log.warning(f"Pantalla no disponible tras crear: {name}")
                return

            # Ocultar anterior (si existe) y mostrar nueva
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
            log.info(f"Cambiado a pantalla: {name}")
        except Exception as e:
            log.error(f"Error cambiando a pantalla {name}: {e}")
    
    def _create_screen(self, name: str):
        """Crea una pantalla bajo demanda."""
        try:
            if name == 'home':
                try:
                    focus = bool(self._cfg.get('focus_mode', True))
                except Exception:
                    focus = True
                if focus:
                    from bascula.ui.focus_screen import FocusScreen
                    self.screens[name] = FocusScreen(self.root, self)
                else:
                    self.screens[name] = HomeScreen(self.root, self,
                                                    on_open_settings_menu=lambda: self.show_screen('settingsmenu'))
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
            log.error(f"Error creando pantalla {name}: {e}")
    
            # Determinar baudrate
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
            
            # Factor de calibración
            calib_factor = 1.0
            if self._cfg:
                try:
                    calib_factor = float(self._cfg.get('calib_factor', 1.0))
                except (ValueError, TypeError):
                    calib_factor = 1.0
            
            log.info(f"Configuración final: port={port}, baud={baud}, calib_factor={calib_factor}")
            
            # Inicializar TareManager
            log.info("Inicializando TareManager...")
            try:
                self.tare = TareManager(calib_factor=calib_factor)
                log.info("✓ TareManager inicializado correctamente")
            except Exception as e:
                log.error(f"Error inicializando TareManager: {e}")
                self.tare = None
            
            # Inicializar ScaleService
            log.info("Inicializando ScaleService...")
            try:
                # Crear ScaleService con parámetros compatibles
                scale_params = {
                    'port': port,
                    'baud': baud
                }
                
                # Añadir logger si el constructor lo acepta
                import inspect
                try:
                    sig = inspect.signature(ScaleService.__init__)
                    if 'logger' in sig.parameters:
                        scale_params['logger'] = log
                    if 'fail_fast' in sig.parameters:
                        scale_params['fail_fast'] = False
                except Exception:
                    pass
                
                log.info(f"Creando ScaleService con parámetros: {scale_params}")
                self.reader = ScaleService(**scale_params)
                
                # Intentar iniciar
                log.info("Llamando a ScaleService.start()...")
                start_result = self.reader.start()
                log.info(f"ScaleService.start() resultado: {start_result}")
                
                # Verificar que funciona
                if start_result is not False:
                    try:
                        test_weight = self.reader.get_latest() if hasattr(self.reader, 'get_latest') else None
                        log.info(f"Test inicial de peso: {test_weight}")
                        log.info("✓ ScaleService inicializado y funcionando")
                    except Exception as e:
                        log.warning(f"Test de peso falló: {e}")
                else:
                    raise RuntimeError("ScaleService.start() devolvió False")
                    
            except Exception as e:
                log.error(f"Error crítico con ScaleService: {e}")
                log.error("Continuando sin hardware de báscula")
                self.reader = None
        
        except Exception as e:
            log.error(f"Error crítico en inicialización serie: {e}")
            self.reader = None
            self.tare = None
    
    def _init_audio_service(self):
        """Inicializa el servicio de audio."""
        if self.splash:
            self.root.after(0, lambda: self.splash.set_status("Configurando audio..."))
        
        try:
            self.audio = AudioService(cfg=self._cfg, logger=log)
            self.audio.update_config(self._cfg)
            if self._cfg.get('sound_enabled', True):
                self.audio.play_event('boot_ready')
            log.info("Audio inicializado")
        except Exception as e:
            log.warning(f"Audio no disponible: {e}")
    
    def _init_voice_services(self):
        """Inicializa servicios de voz."""
        try:
            if self._cfg.get('wakeword_enabled', False):
                self.wakeword = PorcupineWakeWord()
                self.wakeword.start()
                log.info("Wake word activada")
        except Exception as e:
            log.warning(f"Wake word no disponible: {e}")
        
        try:
            self.voice = VoiceService()
            log.info("Servicio de voz listo")
        except Exception as e:
            log.warning(f"Voz no disponible: {e}")
    
    def _init_camera_service(self):
        """Inicializa el servicio de cámara."""
        if self.splash:
            self.root.after(0, lambda: self.splash.set_status("Preparando cámara..."))
        
        try:
            self.camera = CameraService()
            if self.camera.available():
                log.info("Cámara disponible")
            else:
                log.info("Cámara no detectada")
        except Exception as e:
            log.info(f"Cámara no disponible: {e}")
    
    def _init_photo_manager(self):
        """Inicializa el gestor de fotos."""
        try:
            self.photo_manager = PhotoManager(logger=log)
            if self.camera and self.camera.available() and self.camera.picam:
                self.photo_manager.attach_camera(self.camera.picam)
            
            if not self._cfg.get('keep_photos', False):
                self.photo_manager.clear_all()
            
            log.info("Gestor de fotos inicializado")
        except Exception as e:
            log.warning(f"Gestor de fotos no disponible: {e}")
    
    def _init_vision_service(self):
        """Inicializa el servicio de visión."""
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
        
        # Cargar alimentos locales
        try:
            from bascula.domain.foods import load_foods
            self.foods = load_foods()
        except Exception:
            self.foods = []
    
    def _init_nightscout_queue(self):
        """Inicializa la cola offline de Nightscout."""
        try:
            ns_file = Path.home() / ".config" / "bascula" / "nightscout.json"
            if ns_file.exists():
                import json
                cfg = json.loads(ns_file.read_text(encoding="utf-8"))
                url = (cfg.get('url') or '').strip()
                tok = (cfg.get('token') or '').strip()
                if url:
                    offqueue_retry(url, tok)
                    
                    # Network watcher para reintentos automáticos
                    def _net_watch():
                        try:
                            import requests
                            last_ok = False
                            while True:
                                try:
                                    r = requests.get(f"{url}/api/v1/status.json", timeout=5)
                                    ok = r.ok
                                except requests.exceptions.RequestException:
                                    ok = False
                                if ok and not last_ok:
                                    offqueue_retry(url, tok)
                                last_ok = ok
                                time.sleep(30)
                        except Exception:
                            pass
                    
                    threading.Thread(target=_net_watch, daemon=True).start()
        except Exception:
            pass
    
    def _on_services_ready(self):
        """Callback cuando los servicios están listos."""
        try:
            # Cerrar splash
            if self.splash:
                self.splash.close()
                self.splash = None
            
            # Mostrar pantalla principal
            self.show_screen('home')

            # Avisos de hardware faltante
            try:
                if not self.reader:
                    self._warn_hw_missing("Báscula no detectada. Revisar conexión serie y reiniciar.")
                elif not BACKEND_AVAILABLE:
                    self._warn_hw_missing("Hardware de báscula en modo simulación.")
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
            
            # Log detallado del estado de servicios
            services_status = {
                'reader': f'OK ({type(self.reader).__name__})' if self.reader else 'NO',
                'tare': f'OK ({type(self.tare).__name__})' if self.tare else 'NO', 
                'camera': 'OK' if (self.camera and self.camera.available()) else 'NO',
                'audio': 'OK' if self.audio else 'NO',
                'voice': 'OK' if self.voice else 'NO',
                'backend_real': 'SI' if BACKEND_AVAILABLE else 'NO'
            }
            log.info(f"Estado servicios: {services_status}")
            
            # Test inmediato del peso
            if self.reader:
                try:
                    test_weight = self.get_latest_weight()
                    log.info(f"Test peso inicial: {test_weight}g")
                except Exception as e:
                    log.error(f"Error en test peso inicial: {e}")
            
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
        """Muestra aviso de hardware faltante."""
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
    
    def _init_services_worker(self):
        """Worker para inicializar servicios."""
        try:
            # Actualizar splash
            if self.splash:
                self.root.after(0, lambda: self.splash.set_status("Iniciando puerto serie..."))
            
            # Inicializar lector serie y tara (usar claves correctas + env overrides)
            try:
                serial_cfg = (self._cfg.get('serial') or {})
                port = os.getenv('SERIAL_DEV') or serial_cfg.get('device') or '/dev/serial0'
                baud = int(os.getenv('SERIAL_BAUD') or serial_cfg.get('baudrate') or 115200)
                calib_factor = float(self._cfg.get('calib_factor', 1.0))
                
                # Inicializar TareManager primero
                self.tare = TareManager(calib_factor=calib_factor)
                
                # ScaleService usa python_backend/serial_scale si existe; si no, modo nulo
                self.reader = ScaleService(port=port, baud=baud, logger=log, fail_fast=False)
                self.reader.start()
                
                log.info(f"Báscula inicializada en {port} @ {baud} (calib_factor={calib_factor})")
            except Exception as e:
                log.error(f"Báscula no disponible: {e}")
                # Sin fallback a mocks - la aplicación debe manejar reader=None
                self.reader = None
                self.tare = None
            
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

            # Avisos de hardware faltante
            try:
                if not self.reader:
                    self._warn_hw_missing("Báscula no detectada. Revisar conexión serie y reiniciar.")
                elif not BACKEND_AVAILABLE:
                    self._warn_hw_missing("Hardware de báscula en modo simulación.")
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
                'voice': 'OK' if self.voice else 'NO'
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
            from pathlib import Path as _P
            from bascula.services.retention import prune_jsonl
            base = _P.home() / '.config' / 'bascula'
            targets = [
                (base / 'recipes.jsonl', 365, 1000, 20*1024*1024),
                (base / 'meals.jsonl',   730, 10000, 100*1024*1024),
                (base / 'offqueue.jsonl',365, 10000, 50*1024*1024),
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
        
        t = threading.Thread(target=heartbeat, daemon=True)
        t.start()

    def _warn_hw_missing(self, msg: str):
        try:
            top = tk.Toplevel(self.root)
            top.title("Aviso")
            top.configure(bg="#141823")
            try: top.attributes("-topmost", True)
            except Exception: pass
            tk.Label(top, text="⚠️  Hardware no disponible", bg="#141823", fg="#ffa500", font=("DejaVu Sans", 14, "bold")).pack(padx=14, pady=(10,4))
            tk.Label(top, text=msg, bg="#141823", fg="#f0f4f8", font=("DejaVu Sans", 12), wraplength=420, justify="left").pack(padx=14, pady=(0,10))
            tk.Button(top, text="Entendido", command=top.destroy, bg="#6b7280", fg="white", bd=0, relief="flat", padx=12, pady=6).pack(pady=(0,10))
            top.update_idletasks()
            # centrar
            x = self.root.winfo_rootx() + (self.root.winfo_width() - top.winfo_width())//2
            y = self.root.winfo_rooty() + (self.root.winfo_height() - top.winfo_height())//3
            top.geometry(f"+{max(0,x)}+{max(0,y)}")
            # autocerrar en 8s
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
            if self.reader:
                if hasattr(self.reader, 'stop'):
                    self.reader.stop()
            if self.camera:
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

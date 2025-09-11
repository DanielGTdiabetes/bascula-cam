#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AplicaciÃ³n principal de BÃ¡scula Digital Pro con UI en Tkinter.
VersiÃ³n simplificada con manejo robusto de errores.
"""
import os
import sys
import time
import threading
import logging
from pathlib import Path
import tkinter as tk

# === IMPORTS BÃSICOS ===
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
    from bascula.services.logging import setup_logging
    from bascula.services.wakeword import PorcupineWakeWord
    from bascula.services.offqueue import retry_all as offqueue_retry
    from bascula.services.voice import VoiceService
    
    log = logging.getLogger(__name__)
    log.info("âœ“ Imports bÃ¡sicos exitosos")
    
except ImportError as e:
    print(f"Error importando mÃ³dulos UI: {e}")
    import logging
    logging.basicConfig(level=logging.INFO)
    log = logging.getLogger(__name__)

# === BACKEND SERIE SIMPLIFICADO ===
# Como no tenemos el backend real, creamos versiones mock
class MockScaleService:
    def __init__(self, *args, **kwargs):
        self.weight = 0.0
        self.stable = False
        
    def start(self): pass
    def stop(self): pass
    def get_weight(self): return self.weight
    def is_stable(self): return self.stable
    def tare(self): return True
    def calibrate(self, weight): return True
    def subscribe(self, callback): pass

class MockSerialReader:
    def __init__(self, *args, **kwargs):
        self.latest = 0.0
        
    def start(self): pass
    def stop(self): pass
    def get_latest(self): return self.latest

class MockTareManager:
    def __init__(self, *args, **kwargs):
        self.offset = 0.0
        
    def apply(self, value): 
        return float(value) - self.offset
    
    def set_tare(self, value): 
        self.offset = float(value)
        
    def update_calib(self, factor): pass

# Intentar importar el backend real, si falla usar mock
try:
    from python_backend.bascula.services.scale import ScaleService
    from python_backend.serial_scale import SerialScale
    BACKEND_AVAILABLE = True
    SerialReader = SerialScale  # Alias para compatibilidad
    TareManager = MockTareManager  # No existe en el backend real
except ImportError:
    try:
        # Intentar importaciÃ³n alternativa
        from bascula.services.scale import ScaleService
        BACKEND_AVAILABLE = True
        SerialReader = MockSerialReader
        TareManager = MockTareManager
    except ImportError:
        ScaleService = MockScaleService
        SerialReader = MockSerialReader
        TareManager = MockTareManager
        BACKEND_AVAILABLE = False
        log.info("Usando clases MOCK para desarrollo")

log = logging.getLogger(__name__)

class BasculaAppTk:
    def __init__(self, root=None):
        """Inicializa la aplicaciÃ³n con manejo robusto de errores."""
        self.root = root or tk.Tk()
        self.root.withdraw()  # Ocultar mientras carga
        
        # ConfiguraciÃ³n de ventana
        self.root.title("BÃ¡scula Digital Pro")
        self.root.configure(bg="#0a0e1a")
        
        # Detectar si estamos en Raspberry Pi
        self.is_rpi = self._detect_rpi()
        
        if self.is_rpi:
            self.root.attributes("-fullscreen", True)
            self.root.config(cursor="none")
        else:
            self.root.geometry("1024x600")
        
        # Servicios
        self.reader = None
        self.tare = None
        self.camera = None
        self.audio = None
        self.photo_manager = None
        self.wakeword = None
        self.voice = None
        self.screens = {}
        self.current_screen = None
        
        # ConfiguraciÃ³n
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
            self.splash = SplashScreen(self.root, title="BÃ¡scula Digital Pro", subtitle="Iniciando servicios...")
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
        """Inicializa el tema al arrancar la aplicaciÃ³n"""
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
        """Retorna la configuraciÃ³n actual."""
        return self._cfg
    
    def save_cfg(self) -> None:
        """Guarda la configuraciÃ³n."""
        try:
            utils.save_config(self._cfg)
            log.info("ConfiguraciÃ³n guardada")
        except Exception as e:
            log.error(f"Error guardando configuraciÃ³n: {e}")
    
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
        """Obtiene el peso actual con tara aplicada."""
        try:
            if self.reader and self.tare:
                raw = self.reader.get_latest()
                if raw is not None:
                    return self.tare.apply(raw)
        except Exception as e:
            log.error(f"Error obteniendo peso: {e}")
        return 0.0
    
    def ensure_camera(self) -> bool:
        """Asegura que la cÃ¡mara estÃ© disponible."""
        if self.camera and self.camera.available():
            return True
        
        try:
            self.camera = CameraService()
            if self.camera.available():
                if self.photo_manager:
                    self.photo_manager.attach_camera(self.camera.picam)
                return True
        except Exception as e:
            log.error(f"Error inicializando cÃ¡mara: {e}")
        
        return False
    
    def capture_image(self) -> str:
        """Captura una imagen y retorna la ruta."""
        if not self.ensure_camera():
            raise RuntimeError("CÃ¡mara no disponible")
        
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
        """Solicita anÃ¡lisis nutricional (placeholder)."""
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
        """Cambia a la pantalla especificada."""
        try:
            if self.current_screen:
                if hasattr(self.current_screen, 'on_hide'):
                    self.current_screen.on_hide()
                self.current_screen.pack_forget()
            
            if name not in self.screens:
                self._create_screen(name)
            
            self.current_screen = self.screens.get(name)
            if self.current_screen:
                self.current_screen.pack(fill="both", expand=True)
                if hasattr(self.current_screen, 'on_show'):
                    self.current_screen.on_show()
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
    
    def _init_services_bg(self):
        """Inicializa servicios en segundo plano."""
        t = threading.Thread(target=self._init_services_worker, daemon=True)
        t.start()
    
    def _init_services_worker(self):
        """Worker para inicializar servicios."""
        try:
            # Actualizar splash
            if self.splash:
                self.root.after(0, lambda: self.splash.set_status("Iniciando puerto serie..."))
            
            # Inicializar lector serie (mock en desarrollo)
            try:
                port = self._cfg.get('port', '/dev/serial0')
                baud = self._cfg.get('baud', 115200)
                
                self.reader = SerialReader(port=port, baudrate=baud)
                self.tare = TareManager(calib_factor=self._cfg.get('calib_factor', 1.0))
                
                if hasattr(self.reader, 'start'):
                    self.reader.start()
                
                log.info(f"BÃ¡scula inicializada en {port}")
            except Exception as e:
                log.warning(f"BÃ¡scula no disponible: {e}")
                # Usar mock para desarrollo
                self.reader = MockSerialReader()
                self.tare = MockTareManager()
            
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
                self.root.after(0, lambda: self.splash.set_status("Preparando cÃ¡mara..."))
            
            # Inicializar cÃ¡mara (opcional)
            try:
                self.camera = CameraService()
                if self.camera.available():
                    log.info("camara disponible")
                else:
                    log.info("CÃ¡mara no detectada")
            except Exception as e:
                log.info(f"CÃ¡mara no disponible: {e}")
            
            # Inicializar gestor de fotos
            try:
                self.photo_manager = PhotoManager(logger=log)
                if self.camera and self.camera.available():
                    self.photo_manager.attach_camera(self.camera.picam)
                
                if not self._cfg.get('keep_photos', False):
                    self.photo_manager.clear_all()
                
                log.info("Gestor de fotos inicializado")
            except Exception as e:
                log.warning(f"Gestor de fotos no disponible: {e}")
            
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
                                    ok = bool(getattr(r, 'ok', False))
                                except Exception:
                                    ok = False
                                if ok and not last_ok:
                                    offqueue_retry(url, tok)
                                last_ok = ok
                                _t.sleep(30)
                        threading.Thread(target=_net_watch, daemon=True).start()
            except Exception:
                pass
            
        except Exception as e:
            log.error(f"Error crÃ­tico inicializando servicios: {e}")
            self.root.after(0, self._show_error_screen, str(e))
    
    def _on_services_ready(self):
        """Callback cuando los servicios estÃ¡n listos."""
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
            self.root.focus_force()
            
            log.info("AplicaciÃ³n lista")
            
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
        
        tk.Label(frame, text="âš  Error de InicializaciÃ³n", 
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
        """Reintenta la inicializaciÃ³n."""
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
        """Ejecuta el loop principal de la aplicaciÃ³n."""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            log.info("AplicaciÃ³n interrumpida por usuario")
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
    
    # Crear y ejecutar aplicaciÃ³n
    try:
        app = BasculaAppTk()
        app.run()
    except Exception as e:
        log.error(f"Error fatal: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()


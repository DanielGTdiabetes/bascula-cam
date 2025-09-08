#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aplicación principal de Báscula Digital Pro con UI en Tkinter.
Versión corregida con manejo de errores mejorado.
"""
import os
import sys
import time
import threading
import logging
from pathlib import Path
import tkinter as tk

# Asegurar que python_backend está en el path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from bascula import utils
    from bascula.ui.splash import SplashScreen
    from bascula.ui.screens import HomeScreen, CalibScreen
    from bascula.ui.screens_ext import (
        WifiScreen, ApiKeyScreen, NightscoutScreen, 
        DiabetesSettingsScreen, SettingsMenuScreenLegacy
    )
    from bascula.ui.screens_tabs_ext import TabbedSettingsMenuScreen
    from bascula.services.camera import CameraService
    from bascula.services.audio import AudioService
    from bascula.services.photo_manager import PhotoManager
    from bascula.services.logging import setup_logging
except ImportError as e:
    print(f"Error importando módulos UI: {e}")
    # Importaciones mínimas para mostrar error
    import tkinter as tk
    from bascula.services.logging import setup_logging

# Intentar importar el servicio de báscula del backend
try:
    from python_backend.bascula.reader import SerialReader
    from python_backend.bascula.tare import TareManager
except ImportError as e:
    print(f"Advertencia: No se pudo importar el backend serie: {e}")
    SerialReader = None
    TareManager = None

log = logging.getLogger(__name__)

class BasculaAppTk:
    def __init__(self, root=None):
        """Inicializa la aplicación con manejo robusto de errores."""
        self.root = root or tk.Tk()
        self.root.withdraw()  # Ocultar mientras carga
        
        # Configuración de ventana
        self.root.title("Báscula Digital Pro")
        self.root.configure(bg="#0a0e1a")
        
        # Detectar si estamos en Raspberry Pi
        self.is_rpi = self._detect_rpi()
        
        if self.is_rpi:
            # Pantalla completa en RPi
            self.root.attributes("-fullscreen", True)
            self.root.config(cursor="none")
        else:
            # Ventana normal en desarrollo
            self.root.geometry("1024x600")
        
        # Servicios
        self.reader = None
        self.tare = None
        self.camera = None
        self.audio = None
        self.photo_manager = None
        self.screens = {}
        self.current_screen = None
        
        # Configuración
        self._cfg = utils.load_config()
        
        # Splash screen
        self.splash = None
        try:
            self.splash = SplashScreen(self.root, title="Báscula Digital Pro", subtitle="Iniciando servicios...")
            self.splash.update()
        except Exception as e:
            log.warning(f"No se pudo crear splash screen: {e}")
        
        # Iniciar servicios en segundo plano
        self._init_services_bg()
    
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
        """Asegura que la cámara esté disponible."""
        if self.camera and self.camera.available():
            return True
        
        try:
            self.camera = CameraService()
            if self.camera.available():
                if self.photo_manager:
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
        # Aquí iría la integración con API de nutrición
        # Por ahora retornamos datos de ejemplo
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
                self.screens[name] = HomeScreen(self.root, self, 
                                               on_open_settings_menu=lambda: self.show_screen('settingsmenu'))
            elif name == 'calib':
                self.screens[name] = CalibScreen(self.root, self)
            elif name == 'settingsmenu':
                # Usar versión con tabs si está disponible
                try:
                    self.screens[name] = TabbedSettingsMenuScreen(self.root, self)
                except:
                    self.screens[name] = SettingsMenuScreenLegacy(self.root, self)
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
            
            # Inicializar lector serie
            if SerialReader and TareManager:
                try:
                    port = self._cfg.get('port', '/dev/serial0')
                    baud = self._cfg.get('baud', 115200)
                    smoothing = self._cfg.get('smoothing', 5)
                    
                    self.reader = SerialReader(
                        port=port,
                        baudrate=baud,
                        smoothing=smoothing,
                        logger=log
                    )
                    
                    calib_factor = self._cfg.get('calib_factor', 1.0)
                    self.tare = TareManager(calib_factor=calib_factor)
                    
                    log.info(f"Báscula inicializada en {port}")
                except Exception as e:
                    log.error(f"Error inicializando báscula: {e}")
                    # Continuar sin báscula para desarrollo
            
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
            
            # Actualizar splash
            if self.splash:
                self.root.after(0, lambda: self.splash.set_status("Preparando cámara..."))
            
            # Inicializar cámara (opcional)
            try:
                self.camera = CameraService()
                if self.camera.available():
                    log.info("Cámara disponible")
                else:
                    log.info("Cámara no detectada")
            except Exception as e:
                log.info(f"Cámara no disponible: {e}")
            
            # Inicializar gestor de fotos
            try:
                self.photo_manager = PhotoManager(logger=log)
                if self.camera and self.camera.available():
                    self.photo_manager.attach_camera(self.camera.picam)
                
                # Limpiar fotos al inicio si no está habilitado keep_photos
                if not self._cfg.get('keep_photos', False):
                    self.photo_manager.clear_all()
                
                log.info("Gestor de fotos inicializado")
            except Exception as e:
                log.warning(f"Gestor de fotos no disponible: {e}")
            
            # Actualizar splash
            if self.splash:
                self.root.after(0, lambda: self.splash.set_status("Cargando interfaz..."))
            
            # Esperar un momento para que se vea el splash
            time.sleep(0.5)
            
            # Construir UI en el hilo principal
            self.root.after(0, self._on_services_ready)
            
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
            
            # Mostrar ventana
            self.root.deiconify()
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

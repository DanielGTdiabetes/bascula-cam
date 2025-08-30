# -*- coding: utf-8 -*-
"""
Bascula UI - Tk launcher estable con soporte de escala y modo kiosko.

Características clave:
- Escalado automático basado en resolución real de pantalla
- Modo kiosko sin parpadeos: borderless (overrideredirect)
- Variables de entorno:
    BASCULA_SCALING   -> "auto" (por defecto, recomendado)
    BASCULA_FULLSCREEN-> "1" o "0" (por defecto "0"). 
    BASCULA_BORDERLESS-> "1" o "0" (por defecto "1") - recomendado para kiosko
    BASCULA_DEBUG     -> "1" o "0" (overlay con Screen/Window/scaling)
- Teclas útiles en tiempo de ejecución:
    F11 -> alternar borderless
    Ctrl+q o Escape -> salir
    F1 -> toggle debug overlay
"""

import os
import tkinter as tk
from tkinter import ttk
from serial_reader import SerialReader
from tare_manager import TareManager
from utils import load_config, save_config, MovingAverage

def _env_bool(name: str, default: bool = False) -> bool:
    val = os.environ.get(name, "").strip().lower()
    if val in ("1", "true", "yes", "y", "on"):
        return True
    if val in ("0", "false", "no", "n", "off"):
        return False
    return bool(default)

def _env_str(name: str, default: str) -> str:
    v = os.environ.get(name)
    return v if v is not None else default

class BasculaAppTk:
    """
    Aplicación principal con modo kiosko y escalado automático.
    """

    def __init__(self) -> None:
        # 1) Crear raíz Tk
        self.root = tk.Tk()
        self.root.title("Báscula Digital Pro")
        
        # Variables de entorno
        self._fullscreen = _env_bool("BASCULA_FULLSCREEN", False)
        self._borderless = _env_bool("BASCULA_BORDERLESS", True)
        self._debug = _env_bool("BASCULA_DEBUG", False)
        
        # 2) Configurar para pantalla completa REAL
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        
        print(f"[APP] Resolución detectada: {sw}x{sh}")
        
        # 3) Modo kiosko - APLICAR ANTES de mostrar la ventana
        if self._borderless:
            try:
                self.root.overrideredirect(True)
                print("[APP] Modo borderless activado")
            except Exception as e:
                print(f"[APP] Error borderless: {e}")
        
        if self._fullscreen:
            try:
                self.root.attributes("-fullscreen", True)
                print("[APP] Modo fullscreen activado")
            except Exception as e:
                print(f"[APP] Error fullscreen: {e}")
        
        # Forzar ventana a pantalla completa DESPUÉS del borderless
        self.root.geometry(f"{sw}x{sh}+0+0")
        self.root.resizable(False, False)
        
        # 4) Configurar cierre y teclas
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.bind("<Escape>", lambda e: self._on_close())
        self.root.bind("<Control-q>", lambda e: self._on_close())
        self.root.bind("<F11>", lambda e: self._toggle_borderless())
        self.root.bind("<F1>", lambda e: self._toggle_debug())
        
        # 5) Fondo negro para evitar parpadeos
        self.root.configure(bg="#000000")
        
        # 6) Inicializar servicios
        self._init_services()
        
        # 7) Construir UI
        self._build_ui()
        
        # 8) Overlay de debug opcional - SOLO si está habilitado
        self._overlay = None
        if self._debug:
            print("[APP] Modo debug habilitado - overlay visible")
            self._overlay = self._build_overlay()
            self._tick_overlay()
        else:
            print("[APP] Modo debug deshabilitado - sin overlay")
        
        # 9) Configuración final de ventana
        self.root.focus_force()
        self.root.configure(cursor="none")
        
        # Actualizar geometría una vez más después de todo
        self.root.update_idletasks()
        self.root.geometry(f"{sw}x{sh}+0+0")
        self.root.lift()  # Traer al frente

    def _init_services(self):
        """Inicializa todos los servicios de la aplicación."""
        try:
            # Cargar configuración
            self.cfg = load_config()
            print(f"[APP] Configuración cargada: {self.cfg}")
            
            # Reader serie
            self.reader = SerialReader(
                port=self.cfg.get("port", "/dev/serial0"),
                baud=self.cfg.get("baud", 115200)
            )
            
            # Tare manager
            self.tare = TareManager(
                calib_factor=self.cfg.get("calib_factor", 1.0)
            )
            
            # Suavizado
            self.smoother = MovingAverage(
                size=self.cfg.get("smoothing", 5)
            )
            
            # Iniciar reader
            self.reader.start()
            print("[APP] Servicios iniciados correctamente")
            
        except Exception as e:
            print(f"[APP] Error inicializando servicios: {e}")
            # Crear objetos dummy para evitar errores
            self.cfg = {
                "port": "/dev/serial0",
                "baud": 115200,
                "calib_factor": 1.0,
                "unit": "g",
                "smoothing": 5,
                "decimals": 0
            }
            self.reader = None
            self.tare = TareManager(calib_factor=1.0)
            self.smoother = MovingAverage(size=5)

    def _build_ui(self) -> None:
        """Construye la interfaz principal - VERSIÓN CORREGIDA."""
        # Aplicar escalado automático UNA SOLA VEZ aquí
        try:
            from bascula.ui.widgets import auto_apply_scaling
            auto_apply_scaling(self.root, target=(1024, 600))
            print("[APP] Escalado aplicado correctamente")
        except Exception as e:
            print(f"[APP] Error aplicando escalado: {e}")
        
        # Contenedor principal
        self.main = tk.Frame(self.root, bg="#0a0e1a")
        self.main.pack(fill="both", expand=True)
        
        # Stack de pantallas
        self.screens = {}
        self.current_screen = None
        
        # Importar pantallas
        from bascula.ui.screens import HomeScreen, SettingsScreen
        
        # Crear pantallas
        self.screens["home"] = HomeScreen(
            self.main, self, 
            on_open_settings=lambda: self.show_screen("settings")
        )
        self.screens["settings"] = SettingsScreen(
            self.main, self,
            on_back=lambda: self.show_screen("home")
        )
        
        # Mostrar pantalla inicial
        self.show_screen("home")

    def show_screen(self, name: str):
        """Cambia a la pantalla especificada."""
        if self.current_screen:
            self.current_screen.pack_forget()
        
        if name in self.screens:
            screen = self.screens[name]
            screen.pack(fill="both", expand=True)
            self.current_screen = screen
            
            # Llamar callback on_show si existe
            if hasattr(screen, 'on_show'):
                screen.on_show()

    def _build_overlay(self) -> tk.Label:
        """Overlay de debug."""
        ov = tk.Label(
            self.root,
            text="",
            bg="#000000",
            fg="#00ff00",
            font=("monospace", 10),
            justify="left",
            anchor="nw",
        )
        ov.place(x=5, y=5)
        return ov

    def _tick_overlay(self) -> None:
        """Actualiza overlay de debug."""
        if not self._overlay:
            return
        try:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            ww = self.root.winfo_width()
            wh = self.root.winfo_height()
            
            # Info de la báscula
            weight = self.get_latest_weight()
            stable = self.get_stability()
            
            # Info de servicios
            reader_status = "OK" if (hasattr(self, 'reader') and self.reader) else "ERROR"
            
            txt = f"Screen: {sw}x{sh}\n"
            txt += f"Window: {ww}x{wh}\n"
            txt += f"Weight: {weight:.2f}g\n"
            txt += f"Stable: {stable}\n"
            txt += f"Reader: {reader_status}\n"
            txt += f"Borderless: {self._borderless}\n"
            txt += f"Fullscreen: {self._fullscreen}"
            
            self._overlay.config(text=txt)
        except Exception as e:
            self._overlay.config(text=f"Debug Error: {e}")
        
        self.root.after(1000, self._tick_overlay)

    def _toggle_borderless(self) -> None:
        """Alterna modo borderless."""
        self._borderless = not self._borderless
        try:
            self.root.overrideredirect(self._borderless)
            print(f"[APP] Borderless: {self._borderless}")
        except Exception as e:
            print(f"[APP] Error toggle borderless: {e}")

    def _toggle_debug(self) -> None:
        """Alterna overlay de debug."""
        self._debug = not self._debug
        if self._debug and not self._overlay:
            self._overlay = self._build_overlay()
            self._tick_overlay()
        elif not self._debug and self._overlay:
            self._overlay.destroy()
            self._overlay = None

    def _on_close(self) -> None:
        """Cierre limpio de la aplicación."""
        print("[APP] Cerrando aplicación...")
        try:
            # Detener overlay de debug
            if self._overlay:
                try:
                    self._overlay.destroy()
                except Exception:
                    pass
            
            # Detener reader serie
            if hasattr(self, 'reader') and self.reader:
                self.reader.stop()
                print("[APP] Reader detenido")
            
            # Destruir ventana principal
            self.root.quit()
            self.root.destroy()
            print("[APP] Ventana destruida")
            
        except Exception as e:
            print(f"[APP] Error durante el cierre: {e}")
        finally:
            # Forzar salida si es necesario
            import sys
            sys.exit(0)

    # ============= API para las pantallas =============
    
    def get_cfg(self) -> dict:
        """Obtiene la configuración actual."""
        return self.cfg

    def save_cfg(self) -> None:
        """Guarda la configuración."""
        try:
            save_config(self.cfg)
            print("[APP] Configuración guardada")
        except Exception as e:
            print(f"[APP] Error guardando config: {e}")

    def get_reader(self):
        """Obtiene el reader serie."""
        return self.reader

    def get_tare(self):
        """Obtiene el manager de tara."""
        return self.tare

    def get_smoother(self):
        """Obtiene el suavizador."""
        return self.smoother

    def get_latest_weight(self) -> float:
        """Obtiene el último peso calculado."""
        try:
            if hasattr(self, 'reader') and self.reader:
                raw = self.reader.get_latest()
                if raw is not None:
                    smooth = self.smoother.add(raw)
                    return self.tare.compute_net(smooth)
            return 0.0
        except Exception:
            return 0.0

    def get_stability(self) -> bool:
        """Determina si el peso está estable."""
        try:
            # Implementación simple - en el futuro se puede mejorar
            # con análisis de variación temporal
            if hasattr(self, 'reader') and self.reader:
                # Por ahora siempre retorna False para evitar errores
                return False
            return False
        except Exception:
            return False

    # ============= Bucle principal =============

    def run(self) -> None:
        """Inicia el bucle principal."""
        try:
            # Asegurar posición y tamaño final
            self.root.update_idletasks()
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            self.root.geometry(f"{sw}x{sh}+0+0")
            
            print(f"[APP] Iniciando aplicación en {sw}x{sh}")
            
            # Bucle principal Tkinter
            self.root.mainloop()
            
        except KeyboardInterrupt:
            print("[APP] Interrupción por teclado")
        except Exception as e:
            print(f"[APP] Error en bucle principal: {e}")
        finally:
            # Limpieza final
            print("[APP] Finalizando...")
            try:
                if hasattr(self, 'reader') and self.reader:
                    self.reader.stop()
                    print("[APP] Reader detenido en finally")
            except Exception as e:
                print(f"[APP] Error en limpieza final: {e}")

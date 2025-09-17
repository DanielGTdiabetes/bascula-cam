# -*- coding: utf-8 -*-
import tkinter as tk
import time
import logging

from bascula.config.theme import apply_theme, get_current_colors
from bascula.ui.widgets import TopBar
from bascula.ui.widgets_mascota import MascotaCanvas
from bascula.ui.enhanced_topbar import EnhancedTopBar
from bascula.ui.navigation import NavigationManager
from bascula.ui.transitions import TransitionManager, TransitionType
# Intento de importar pantallas reales; si falla, usaremos placeholders
try:
    from bascula.ui import screens  # HomeScreen, ScaleScreen, ScannerScreen, SettingsScreen, TimerPopup
    _ = (screens.HomeScreen, screens.ScaleScreen, screens.ScannerScreen, screens.SettingsScreen)
except Exception:
    screens = None

from bascula.ui.mascot_messages import MascotMessenger
from bascula.services.event_bus import EventBus
from bascula.services.mascot_brain import MascotBrain
from bascula.services.llm_client import LLMClient
from bascula.state import AppState

logger = logging.getLogger(__name__)


class BasculaApp:
    """App principal Tkinter de Bascula-Cam (versión robusta)"""

    def __init__(self, theme: str = 'modern') -> None:
        # Raíz y tema con configuración robusta para kiosk
        self.root = tk.Tk()
        self.root.title('Báscula Cam')
        
        # Configuración específica para kiosk mode
        self.root.attributes('-fullscreen', True)
        self.root.configure(cursor='none')  # Ocultar cursor
        self.root.focus_set()
        
        # Fallback geometry si fullscreen falla
        try:
            self.root.geometry('1024x600')
            self.root.resizable(False, False)
        except Exception:
            pass
        
        # Asegurar que la ventana esté al frente
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after_idle(lambda: self.root.attributes('-topmost', False))

        # Estado y propiedades base
        self.state = AppState()
        self.screens = {}
        self.current_screen = None
        self.current_screen_name = "home"
        self.sound_on = True
        self.timer_job = None
        self.timer_end = 0.0
        self.hypo_timer_job = None
        self.diabetic_mode = False
        self.auto_capture_enabled = True
        self.auto_capture_min_delta_g = 8.0
        self.bg_monitor = None
        self._recipe_overlay = None
        self._last_low_alarm_ts = 0.0
        self._last_high_alarm_ts = 0.0
        self._last_nightscout_err_ts = 0.0
        self.last_capture_g = None
        self.bg_value = None
        self.bg_trend = None
        self.reader = None
        self.tare_manager = None
        self.camera = None
        self.audio = None

        # Tema y fondo
        self.theme_name = theme
        apply_theme(self.root, theme)
        pal = get_current_colors()
        self.root.configure(bg=pal['COL_BG'])

        # Navigation manager and transition system
        self.navigation_manager = NavigationManager(self)
        
        # Enhanced topbar with navigation - fallback to regular topbar if enhanced fails
        try:
            self.topbar = EnhancedTopBar(self.root, app=self, navigation_manager=self.navigation_manager)
            self.topbar.pack(fill='x')
        except Exception as e:
            logger.warning(f"Enhanced topbar failed, using regular topbar: {e}")
            self.topbar = TopBar(self.root, app=self)
            self.topbar.pack(fill='x')
        
        # Screen container with transition support
        self.screen_container = tk.Frame(self.root, bg=pal['COL_BG'])
        self.screen_container.pack(fill='both', expand=True)
        
        # Transition manager for smooth screen changes - with fallback
        try:
            self.transition_manager = TransitionManager(self.screen_container)
        except Exception as e:
            logger.warning(f"Transition manager failed, using direct screen changes: {e}")
            self.transition_manager = None

        # Host de mascota por encima de pantallas
        self.mascot_host = tk.Frame(self.screen_container, bg=pal['COL_BG'])
        self.mascot_host.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.mascot_host.lower()
        self.mascot = MascotaCanvas(self.mascot_host, width=300, height=300, with_legs=True)
        self.mascot.place(x=362, y=150)

        # Messenger/brain/eventos/LLM tolerante
        self.messenger = MascotMessenger(
            get_mascot_widget=lambda: self.current_mascot_widget(),
            get_topbar=lambda: getattr(self, "topbar", None),
            theme_colors=pal,
        )
        self.event_bus = EventBus()
        try:
            api_key = self.get_cfg().get("llm_api_key")
            self.llm_client = LLMClient(api_key) if api_key else None
        except Exception:
            self.llm_client = None
        self.mascot_brain = MascotBrain(self, self.event_bus)

        # Fallback visual para evitar blanco - más visible
        self._boot_label = tk.Label(self.root, text="🔄 Iniciando Báscula Digital Pro...",
                                    fg="#00ff66", bg=pal['COL_BG'], 
                                    font=("DejaVu Sans", 24, "bold"))
        self._boot_label.pack(expand=True)
        
        # Forzar actualización visual inmediata
        self.root.update_idletasks()
        self.root.update()

        # Servicios tolerantes
        self._init_services()

        # Pantalla inicial + idle
        self.show_screen('home')
        self.root.after(20000, self._idle_tick)

    # ---------- helpers mascota ----------
    def current_mascot_widget(self):
        """Return the current mascot widget for messenger"""
        if self.current_screen is not None:
            for attr in ("mascot", "mascota"):
                widget = getattr(self.current_screen, attr, None)
                if widget is not None:
                    return widget.as_widget() if hasattr(widget, "as_widget") else widget
        return self.mascot

    def _remove_boot_label(self) -> None:
        label = getattr(self, '_boot_label', None)
        if label is not None:
            try:
                label.destroy()
            except Exception:
                pass
            self._boot_label = None

    # ---------- servicios ----------
    def _init_services(self):
        cfg = self.get_cfg()
        # Báscula
        try:
            from bascula.services.scale import ScaleService
            self.reader = ScaleService(port=cfg.get('port', '/dev/serial0'),
                                       baud=cfg.get('baud', 115200),
                                       fail_fast=False)
            self.reader.start()
        except Exception as e:
            logger.warning(f"Scale service not available: {e}")
            self.reader = None
        # Tara
        try:
            from bascula.services.tare_manager import TareManager
            self.tare_manager = TareManager(calib_factor=cfg.get('calib_factor', 1.0),
                                            min_display=0.0)
        except Exception as e:
            logger.warning(f"Tare manager not available: {e}")
            self.tare_manager = None
        # Audio
        try:
            from bascula.services.audio import AudioService
            self.audio = AudioService(cfg, logger)
        except Exception as e:
            logger.warning(f"Audio service not available: {e}")
            self.audio = None
        # Cámara
        try:
            from bascula.services.camera import CameraService
            self.camera = CameraService()
        except Exception as e:
            logger.warning(f"Camera service not available: {e}")
            self.camera = None

    # ---------- pantallas / navegación ----------
    def _set_screen(self, scr: tk.Frame) -> None:
        if self.current_screen is not None:
            try:
                if hasattr(self.current_screen, 'on_hide'):
                    self.current_screen.on_hide()
            except Exception:
                pass
            self.current_screen.destroy()
        self.current_screen = scr
        self.current_screen.pack(fill='both', expand=True)
        # quita fallback
        self._remove_boot_label()
        # mascota por encima
        self.mascot_host.lift()
        self.current_screen_name = getattr(scr, "name", scr.__class__.__name__)

    def show_screen(self, screen_name: str, use_transition: bool = True, 
                   transition_type: TransitionType = TransitionType.FADE):
        try:
            if screen_name not in self.screens:
                self._create_screen(screen_name)
            
            new_screen = self.screens[screen_name]
            
            # Update navigation manager
            if hasattr(self, 'navigation_manager'):
                self.navigation_manager.current_screen = screen_name
                # Update breadcrumbs in topbar
                if hasattr(self.topbar, 'update_breadcrumbs'):
                    self.topbar.update_breadcrumbs(screen_name)
            
            # Use transition if enabled and available
            if (use_transition and hasattr(self, 'transition_manager') and 
                self.transition_manager is not None and 
                not self.transition_manager.is_transition_active()):
                def on_transition_complete():
                    self.current_screen = new_screen
                    self.current_screen_name = getattr(new_screen, "name", new_screen.__class__.__name__)
                    self._remove_boot_label()
                    self.mascot_host.lift()
                
                success = self.transition_manager.transition_to_screen(
                    new_screen, transition_type, callback=on_transition_complete)
                
                if success:
                    return
            
            # Fallback to immediate screen change
            if self.current_screen:
                self.current_screen.pack_forget()
            
            # Remove boot label if still present
            self._remove_boot_label()
            
            new_screen.pack(fill='both', expand=True)
            self.current_screen = new_screen
            self.current_screen_name = getattr(new_screen, "name", new_screen.__class__.__name__)
            self.mascot_host.lift()
            
        except Exception as e:
            logger.error(f"Error showing screen {screen_name}: {e}")
            # Fallback a home si hay error
            if screen_name != 'home':
                self.show_screen('home', use_transition=False)

    def _create_screen(self, screen_name: str):
        pal = get_current_colors()
        try:
            if screen_name == 'home':
                if self.get_cfg().get('focus_mode', True):
                    try:
                        from bascula.ui.focus_screen import FocusScreen
                        self.screens['home'] = FocusScreen(self.screen_container, self)
                    except Exception as e:
                        logger.error("Failed to create screen home (focus): %s", e)
                        if screens:
                            self.screens['home'] = screens.HomeScreen(self.screen_container, self)
                        else:
                            f = tk.Frame(self.screen_container, bg=pal['COL_BG'])
                            tk.Label(f, text="Home no disponible", fg="#EEE", bg=pal['COL_BG']).pack(pady=20)
                            self.screens['home'] = f
                else:
                    if screens:
                        self.screens['home'] = screens.HomeScreen(self.screen_container, self)
                    else:
                        f = tk.Frame(self.screen_container, bg=pal['COL_BG'])
                        tk.Label(f, text="Home no disponible", fg="#EEE", bg=pal['COL_BG']).pack(pady=20)
                        self.screens['home'] = f
                return

            elif screen_name == 'scale' and screens:
                self.screens['scale'] = screens.ScaleScreen(self.screen_container, self)
            elif screen_name == 'scanner' and screens:
                self.screens['scanner'] = screens.ScannerScreen(self.screen_container, self)
            elif screen_name == 'settings' and screens:
                self.screens['settings'] = screens.SettingsScreen(
                    self.screen_container, self,
                    self.get_state, self.set_state,
                    self.change_theme, lambda: self.show_screen('home')
                )
            elif screen_name == 'settingsmenu':
                from bascula.ui.screens_tabs_ext import TabbedSettingsMenuScreen
                self.screens[screen_name] = TabbedSettingsMenuScreen(self.screen_container, self)
            elif screen_name == 'wifi':
                from bascula.ui.screens_wifi import WifiScreen
                self.screens[screen_name] = WifiScreen(self.screen_container, self)
            elif screen_name == 'nightscout':
                from bascula.ui.screens_nightscout import NightscoutScreen
                self.screens[screen_name] = NightscoutScreen(self.screen_container, self)
            elif screen_name == 'apikey':
                from bascula.ui.screens_apikey import ApiKeyScreen
                self.screens[screen_name] = ApiKeyScreen(self.screen_container, self)
            elif screen_name == 'diabetes':
                from bascula.ui.screens_diabetes import DiabetesSettingsScreen
                self.screens[screen_name] = DiabetesSettingsScreen(self.screen_container, self)
            elif screen_name == 'history':
                from bascula.ui.history_screen import HistoryScreen
                self.screens[screen_name] = HistoryScreen(self.screen_container, self)
            elif screen_name == 'calib':
                self.screens[screen_name] = self._create_calib_screen()
        except Exception as e:
            logger.error("Failed to create screen %s: %s", screen_name, e)
            if screen_name == 'home' and screens:
                # Asegurar siempre una pantalla visible
                self.screens['home'] = screens.HomeScreen(self.screen_container, self)

    def _create_calib_screen(self):
        pal = get_current_colors()
        f = tk.Frame(self.screen_container, bg=pal['COL_BG'])
        tk.Label(f, text="Calibración", fg=pal['COL_TEXT'], bg=pal['COL_BG'],
                 font=("DejaVu Sans", 24)).pack(pady=20)
        tk.Button(f, text="Volver", command=lambda: self.show_screen('settingsmenu')).pack()
        return f

    def show_main(self) -> None:
        self.topbar.set_message('')
        self.show_screen('home')

    def show_scale(self): self.show_screen('scale')
    def show_scanner(self): self.show_screen('scanner')
    def show_settings(self): self.show_screen('settingsmenu')

    def open_timer_popup(self):
        if screens and hasattr(screens, "TimerPopup"):
            screens.TimerPopup(self)

    def open_scanner(self): self.show_scanner()
    def open_settings(self): self.show_settings()

    def open_recipes(self):
        if self._recipe_overlay is None:
            try:
                from bascula.ui.overlay_recipe import RecipeOverlay
                self._recipe_overlay = RecipeOverlay(self.root, self)
            except Exception as e:
                logger.warning(f"Recipe overlay not available: {e}")
                return
        self._recipe_overlay.show()

    def _center_coords(self, size: int) -> tuple[int, int]:
        self.root.update_idletasks()
        w = self.screen_container.winfo_width() or 1024
        h = self.screen_container.winfo_height() or 600
        return (w - size) // 2, (h - size) // 2

    def _corner_coords(self, size: int = 140) -> tuple[int, int]:
        self.root.update_idletasks()
        w = self.screen_container.winfo_width() or 1024
        return w - size - 16, 16

    # ---------- acciones báscula ----------
    def zero_scale(self) -> None:
        if hasattr(self, 'messenger'):
            self.messenger.show("Cero aplicado", kind='info', priority=4, icon='ℹ️')
        self.event_bus.publish("TARA")

    def tare_scale(self) -> None:
        if hasattr(self, 'messenger'):
            self.messenger.show("Tara aplicada", kind='info', priority=4, icon='ℹ️')
        self.event_bus.publish("TARA")

    def toggle_unit(self) -> None:
        if screens and isinstance(self.current_screen, getattr(screens, "ScaleScreen", tuple())):
            try:
                self.current_screen._toggle_unit()
            except Exception:
                pass

    def toggle_sound(self) -> None:
        self.sound_on = not self.sound_on
        try:
            self.topbar.sound_btn.config(text='🔊' if self.sound_on else '🔇')
        except Exception:
            pass

    # ---------- temporizador ----------
    def start_timer(self, seconds: int) -> None:
        self.timer_end = time.time() + seconds
        self.event_bus.publish("TIMER_STARTED", seconds)
        self._update_timer()

    def _update_timer(self) -> None:
        remaining = int(self.timer_end - time.time())
        if remaining <= 0:
            try:
                self.topbar.set_timer('')
            except Exception:
                pass
            if self.timer_job:
                try:
                    self.root.after_cancel(self.timer_job)
                except Exception:
                    pass
            self.event_bus.publish("TIMER_FINISHED")
            return
        m, s = divmod(remaining, 60)
        try:
            self.topbar.set_timer(f"{m:02d}:{s:02d}")
        except Exception:
            pass
        self.timer_job = self.root.after(1000, self._update_timer)

    # ---------- estado y tema ----------
    def get_state(self) -> dict:
        return {
            "theme": self.theme_name,
            "diabetic_mode": self.diabetic_mode,
            "auto_capture_enabled": self.auto_capture_enabled,
            "auto_capture_min_delta_g": self.auto_capture_min_delta_g,
            "timer_active": bool(self.timer_job),
            "last_capture_g": self.last_capture_g,
            "bg_value": self.bg_value,
            "bg_trend": self.bg_trend,
        }

    def set_state(self, state: dict) -> None:
        if 'theme' in state:
            self.change_theme(state['theme'])
        if 'diabetic_mode' in state:
            self.set_diabetic_mode(state['diabetic_mode'])
        if 'auto_capture_enabled' in state:
            self.auto_capture_enabled = bool(state['auto_capture_enabled'])
        if 'auto_capture_min_delta_g' in state:
            try:
                self.auto_capture_min_delta_g = float(state['auto_capture_min_delta_g'])
            except Exception:
                pass

    def change_theme(self, name: str) -> None:
        self.theme_name = name
        apply_theme(self.root, name)
        try:
            self.messenger.pal = get_current_colors()
            self.event_bus.publish("THEME_CHANGED", name)
        except Exception:
            pass

    # ---------- BG / modo diabético ----------
    def set_diabetic_mode(self, enabled: bool) -> None:
        self.diabetic_mode = enabled
        if not enabled:
            if self.bg_monitor:
                try:
                    self.bg_monitor.stop()
                except Exception:
                    pass
                self.bg_monitor = None
            try:
                self.topbar.set_bg(None)
            except Exception:
                pass
        else:
            try:
                from bascula.services.bg_monitor import BgMonitor  # import en el lugar correcto
                interval = int(self.get_cfg().get('bg_poll_s', 60))
                self.bg_monitor = BgMonitor(self, interval_s=interval)
                self.bg_monitor.start()
                self.topbar.set_bg('---')
            except Exception as e:
                logger.warning(f"BG monitor not available: {e}")

    def on_bg_update(self, value_mgdl: int, trend: str) -> None:
        try:
            self.topbar.set_bg(str(value_mgdl), trend)
        except Exception:
            pass
        self.bg_value = value_mgdl
        self.bg_trend = trend
        self.event_bus.publish("BG_UPDATE", {"bg": value_mgdl, "trend": trend})

    def on_bg_error(self, msg: str):
        try:
            if hasattr(self, 'messenger'):
                self.messenger.show(msg, kind="info", priority=2, icon="ℹ️")
            else:
                self.topbar.set_message(msg)
        except Exception:
            pass

    # ---------- cfg y servicios ----------
    def get_cfg(self) -> dict:
        """Get current configuration with all needed keys"""
        try:
            from bascula.utils import load_config, DEFAULT_CONFIG
            cfg = load_config()
            defaults = dict(DEFAULT_CONFIG)
        except Exception:
            cfg = {}
            defaults = {}
        # defaults adicionales necesarios por la app
        defaults.update({
            'focus_mode': True,
            'llm_api_key': '',
            'mascot_persona': 'discreto',
            'mascot_max_per_hour': 3,
            'mascot_dnd': False,
            'mascot_llm_enabled': False,
            'mascot_llm_send_health': False,
            'theme_scanlines': False,
            'theme_glow': False,
            'textfx_enabled': True,
            'vision_autosuggest_enabled': False,
            'vision_confidence_threshold': 0.85,
            'vision_min_weight_g': 20,
            'wakeword_enabled': False,
            'piper_model': '',
            'piper_enabled': False,
            'foodshot_size': '4608x2592',
            'port': '/dev/serial0',
            'baud': 115200,
            'calib_factor': 1.0,
            'bg_low_mgdl': 70,
            'bg_high_mgdl': 180,
            'bg_poll_s': 60,
        })
        for k, v in defaults.items():
            cfg.setdefault(k, v)
        return cfg

    def save_cfg(self) -> None:
        try:
            from bascula.utils import save_config
            save_config(self.get_cfg())
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def get_reader(self): return self.reader
    def get_tare(self): return self.tare_manager
    def get_audio(self): return self.audio

    def get_latest_weight(self) -> float:
        if self.reader and self.tare_manager:
            raw = self.reader.get_latest()
            if raw is not None:
                return self.tare_manager.compute_net(raw)
        return 0.0

    # ---------- ciclo ----------
    def _idle_tick(self) -> None:
        try:
            self.event_bus.publish("IDLE_TICK")
        except Exception:
            pass
        try:
            self.root.after(20000, self._idle_tick)
        except Exception:
            pass

    def run(self):
        """Ejecutar la aplicación con manejo robusto de errores"""
        try:
            # Configuración adicional antes del mainloop
            self.root.protocol("WM_DELETE_WINDOW", self.quit)
            
            # Bind para salir con Escape (útil para desarrollo)
            self.root.bind('<Escape>', lambda e: self.quit())
            
            # Asegurar focus
            self.root.focus_force()
            
            logger.info("Iniciando mainloop de Tkinter")
            self.root.mainloop()
            
        except KeyboardInterrupt:
            logger.info("Aplicación interrumpida por teclado")
            self.quit()
        except Exception as e:
            logger.error(f"Error crítico en la aplicación: {e}", exc_info=True)
            self.quit()

    def quit(self):
        try:
            if self.reader:
                self.reader.stop()
            if self.bg_monitor:
                self.bg_monitor.stop()
            self.save_cfg()
        except Exception:
            pass
        finally:
            try:
                self.root.destroy()
            except Exception:
                pass


# Alias compatibilidad
BasculaAppTk = BasculaApp

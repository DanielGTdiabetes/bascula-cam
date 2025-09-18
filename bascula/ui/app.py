"""High level Tkinter application used by the Báscula Cam kiosk."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import unicodedata
from datetime import datetime
from importlib import import_module
import tkinter as tk
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Iterable, Optional, Sequence, Type

from bascula.config.theme import apply_theme
from bascula.state import AppState
from bascula.domain.foods import upsert_from_off
from bascula.services.bg_monitor import BgMonitor
from bascula.services.event_bus import EventBus
from bascula.services.scale import ScaleService
from bascula.services.tare_manager import TareManager
from bascula.utils import MovingAverage, load_config, save_config
from bascula.ui.mascot_messages import MascotMessenger, get_message
from bascula.ui.transitions import TransitionManager, TransitionType
from bascula.ui.widgets import TopBar, COL_BG, COL_CARD, COL_ACCENT, COL_TEXT, refresh_theme_cache
from bascula.ui.screens import HomeScreen, SettingsScreen
from bascula.ui.scale_screen import ScaleScreen
from bascula.services.treatments import calc_bolus

if TYPE_CHECKING:
    from bascula.ui.mascot import MascotWidget
    from bascula.ui.overlay_favorites import FavoritesOverlay
    from bascula.ui.overlay_recipe import RecipeOverlay
    from bascula.ui.overlay_timer import HypoOverlay, TimerOverlay, TimerPopup

try:  # Optional – audio is not critical during development/testing
    from bascula.services.audio import AudioService
except Exception:  # pragma: no cover - missing optional dependency
    AudioService = None  # type: ignore

try:  # Piper voice feedback for spoken prompts
    from bascula.services.voice import VoiceService
except Exception:  # pragma: no cover - optional
    VoiceService = None  # type: ignore

try:  # Wake word / microphone service
    from bascula.services.wakeword import WakewordService
except Exception:  # pragma: no cover - optional
    WakewordService = None  # type: ignore

try:  # Camera access
    from bascula.services.camera import CameraService
except Exception:  # pragma: no cover - optional
    CameraService = None  # type: ignore

try:  # Vision classifier
    from bascula.services.vision import VisionService
except Exception:  # pragma: no cover - optional
    VisionService = None  # type: ignore

try:  # Barcode helpers
    from bascula.services import barcode as barcode_module
except Exception:  # pragma: no cover - optional
    barcode_module = None  # type: ignore

try:  # LLM client for contextual help
    from bascula.services.llm_client import LLMClient
except Exception:  # pragma: no cover - optional
    LLMClient = None  # type: ignore

try:
    from bascula.services.miniweb import MiniWebService
except Exception:  # pragma: no cover
    MiniWebService = None  # type: ignore

try:
    from bascula.services.ota import OTAService
except Exception:  # pragma: no cover
    OTAService = None  # type: ignore


class _Messenger:
    """Very small helper to route toast-style messages to the log."""

    def __init__(self, logger: logging.Logger) -> None:
        self.logger = logger

    def show(self, text: str, *, kind: str = "info", priority: int = 0, icon: str = "") -> None:
        if not text:
            return
        msg = f"[{kind.upper()}] {text}"
        if icon:
            msg = f"{icon} {msg}"
        self.logger.info(msg)


class BasculaAppTk:
    """Main application orchestrating services and Tk screens."""

    def __init__(self, root: Optional[tk.Tk] = None, theme: str = "modern") -> None:
        self.logger = logging.getLogger("bascula.ui.app")
        self.cfg = load_config()
        self.event_bus = EventBus()
        self.messenger = _Messenger(self.logger)
        self.state = AppState()
        self._transition_pref = str(self.cfg.get("ui_transition", "fade")).lower()
        self.current_screen = None
        self.current_screen_name = ""
        self._mascot_widget: Optional[tk.Widget] = None
        self.mascot: Optional["MascotWidget"] = None
        self._mascot_state: str = "idle"
        self._mascot_sleep_job: Optional[str] = None
        self._mascot_overlay_window: Optional[tk.Toplevel] = None
        self._mascot_overlay_widget: Optional["MascotWidget"] = None
        try:
            self._mascot_sleep_timeout = max(30, int(os.getenv("BASCULA_MASCOT_SLEEP_TIMEOUT", "60") or 60))
        except ValueError:
            self._mascot_sleep_timeout = 60
        self._repo_root = self._resolve_repo_root()
        self.diabetes_mode = bool(self.cfg.get("diabetic_mode", False))
        self._last_bg: Optional[int] = None
        self._last_bg_direction: str = ""
        self._last_bg_ts: Optional[float] = None
        self._bg_pred_15: Optional[int] = None
        self._bg_pred_30: Optional[int] = None
        self._hypo_timer_started_ts: Optional[float] = None
        self.llm_client = None
        if LLMClient is not None:
            try:
                api_key = str(self.cfg.get("llm_api_key") or os.getenv("LLM_API_KEY") or "").strip()
                if api_key:
                    self.llm_client = LLMClient(api_key)
            except Exception:
                self.logger.exception("No se pudo inicializar LLMClient")
                self.llm_client = None

        self.root = root if root is not None else tk.Tk()
        self.root.title("Báscula Cam")
        self.root.minsize(800, 480)

        desired_theme = self.cfg.get("ui_theme", theme)
        self.active_theme = desired_theme
        apply_theme(self.root, desired_theme)

        self.root.configure(bg=COL_BG)
        try:
            self.root.attributes("-fullscreen", True)
        except tk.TclError:
            self.logger.debug("El modo fullscreen no está disponible en este entorno; usando ventana fija")
            self.root.geometry("1024x600")

        # Reactive variables shared by multiple screens
        self.weight_text = tk.StringVar(value="0 g")
        self.stability_text = tk.StringVar(value="Sin lectura")
        self.weight_history: list[dict[str, object]] = []

        # Build UI chrome
        self.topbar = TopBar(self.root, self)
        self.topbar.pack(fill=tk.X)

        self.container = tk.Frame(self.root, bg=COL_BG)
        self.container.pack(fill=tk.BOTH, expand=True)
        self.transition_manager = TransitionManager(self.container)
        self._bind_activity_events()
        self._schedule_mascot_sleep()
        self._voice_nav_enabled = bool(self.cfg.get("voice_prompts", False))
        self._voice_screen_labels: Dict[str, str] = {
            "home": "Inicio",
            "scale": "Pesaje",
            "settings": "Ajustes",
        }
        self._scanner_overlay = None
        self._recipe_overlay: Optional["RecipeOverlay"] = None
        self._timer_overlay: Optional["TimerOverlay"] = None
        self._favorites_overlay: Optional["FavoritesOverlay"] = None
        self._recipe_import_failed = False
        self._timer_import_failed = False
        self._favorites_import_failed = False
        self.meal_items: list[dict[str, Any]] = []
        self._meal_started_ts = time.time()
        self._last_meal_weight = 0.0
        self._gi_cache: dict[str, tuple[str, str]] = {}
        self._gi_table: dict[str, int] = {
            "arroz": 73,
            "arroz blanco": 73,
            "pan": 75,
            "pan blanco": 75,
            "pasta": 50,
            "pasta integral": 45,
            "patata": 85,
            "patata cocida": 82,
            "platano": 60,
            "banana": 60,
            "manzana": 38,
            "pera": 38,
            "zanahoria": 47,
            "zanahoria cocida": 65,
            "avena": 55,
            "leche": 30,
            "leche descremada": 32,
            "yogur": 35,
            "yogur natural": 35,
            "naranja": 43,
            "uva": 59,
            "melon": 65,
            "sandia": 72,
            "garbanzo": 28,
            "lenteja": 32,
            "quinoa": 53,
        }

        self.reader = ScaleService.safe_create(
            logger=self.logger,
            fail_fast=False,
            config=self.cfg,
            port=self.cfg.get("port"),
            baud=int(self.cfg.get("baud", 115200)),
            sample_ms=int(self.cfg.get("sample_ms", 100)),
        )
        self._scale_error_notified = False
        self.tare = TareManager(calib_factor=float(self.cfg.get("calib_factor", 1.0)))
        self._smoothing = MovingAverage(size=max(1, int(self.cfg.get("smoothing", 5))))
        self._last_captured = 0.0
        self._capture_min_delta = float(self.cfg.get("auto_capture_min_delta_g", 8))

        palette = {"COL_CARD": COL_CARD, "COL_TEXT": COL_TEXT, "COL_ACCENT": COL_ACCENT}
        self.mascot_messenger = MascotMessenger(self._get_mascot_widget, lambda: self.topbar, palette)

        # Screen registry ---------------------------------------------------
        self.screens: Dict[str, tk.Frame] = {}
        self._screen_canonical: Dict[str, str] = {}
        self._screen_labels: Dict[str, str] = {}
        self._advanced_screens: Dict[str, str] = {}

        base_screens: Iterable[tuple[str, Type[tk.Frame], str, Sequence[str]]] = (
            ("home", HomeScreen, "Home", (getattr(HomeScreen, "name", "home"),)),
            ("scale", ScaleScreen, "Pesar", (getattr(ScaleScreen, "name", "scale"),)),
            (
                "settings",
                SettingsScreen,
                "Ajustes",
                (getattr(SettingsScreen, "name", "settingsmenu"), "settingsmenu"),
            ),
        )
        for key, screen_cls, label, aliases in base_screens:
            self._register_screen(screen_cls, key=key, label=label, aliases=aliases)

        optional_screens = (
            ("history", "Historial", "bascula.ui.history_screen", "HistoryScreen"),
            ("focus", "Enfoque", "bascula.ui.screens_focus", "FocusScreen"),
            ("nightscout", "Nightscout", "bascula.ui.screens_nightscout", "NightscoutScreen"),
            ("wifi", "Wi-Fi", "bascula.ui.screens_wifi", "WifiScreen"),
            ("apikey", "API Key", "bascula.ui.screens_apikey", "ApiKeyScreen"),
            (
                "diabetes",
                "Diabetes",
                "bascula.ui.screens_diabetes",
                "DiabetesSettingsScreen",
            ),
        )
        for key, label, module_name, class_name in optional_screens:
            self._try_register(key, module_name, class_name, label=label)

        try:
            self.topbar.filter_missing(self.screens)
        except Exception:
            pass

        self.reset_meal()
        self.show_screen("home")

        self.audio = None
        if AudioService is not None:
            try:
                self.audio = AudioService(self.cfg, logger=self.logger)
            except Exception:  # pragma: no cover - optional feature
                self.logger.exception("Fallo inicializando AudioService")
                self.audio = None

        self.voice = None
        if VoiceService is not None:
            try:
                self.voice = VoiceService()
            except Exception:
                self.logger.exception("Fallo inicializando VoiceService")
                self.voice = None

        self.camera = None
        if CameraService is not None:
            try:
                self.camera = CameraService()
            except Exception:
                self.logger.exception("No se pudo iniciar CameraService")
                self.camera = None

        self.vision_service = None
        if VisionService is not None:
            model_path = str(self.cfg.get("vision_model_path") or os.getenv("BASCULA_VISION_MODEL") or "").strip()
            labels_path = str(self.cfg.get("vision_labels_path") or os.getenv("BASCULA_VISION_LABELS") or "").strip()
            if model_path and labels_path:
                try:
                    threshold = float(self.cfg.get("vision_confidence_threshold", 0.85))
                except Exception:
                    threshold = 0.85
                try:
                    self.vision_service = VisionService(model_path, labels_path, confidence_threshold=threshold)
                except Exception:
                    self.logger.exception("No se pudo iniciar VisionService")
                    self.vision_service = None

        self.barcode = barcode_module
        try:
            self.topbar.set_mic_status(False)
        except Exception:
            pass

        self.wake = None
        if WakewordService is not None:
            try:
                self.wake = WakewordService(on_detect=self._on_wake)
                self.wake.start()
                try:
                    self.topbar.set_mic_status(self.wake.is_active())
                except Exception:
                    pass
            except Exception:
                self.logger.exception("No se pudo iniciar WakewordService")
                self.wake = None
                try:
                    self.topbar.set_mic_status(False)
                except Exception:
                    pass
        else:
            try:
                self.topbar.set_mic_status(False)
            except Exception:
                pass

        self.hypo_overlay: Optional["HypoOverlay"] = None
        self.hypo_timer: Optional["TimerPopup"] = None
        try:
            from bascula.ui.overlay_timer import HypoOverlay as _HypoOverlay, TimerPopup as _TimerPopup
        except Exception:
            self.logger.warning("Overlays de temporizador no disponibles", exc_info=True)
            _HypoOverlay = _TimerPopup = None  # type: ignore
        if _HypoOverlay is not None:
            try:
                self.hypo_overlay = _HypoOverlay(self.root, self)
            except Exception:
                self.logger.exception("No se pudo crear el overlay de hipoglucemia")
                self.hypo_overlay = None
        if _TimerPopup is not None:
            try:
                self.hypo_timer = _TimerPopup(self.root, self, duration_s=15 * 60)
            except Exception:
                self.logger.exception("No se pudo crear el temporizador hipoglucemia")
                self.hypo_timer = None
        self.bg_monitor: Optional[BgMonitor] = None
        if self.diabetes_mode:
            self._start_bg_monitor()

        self.miniweb = None
        if MiniWebService is not None:
            try:
                self.miniweb = MiniWebService(self)
                self.miniweb.start()
            except Exception:
                self.logger.exception("No se pudo iniciar el servicio miniweb")
                self.miniweb = None

        self.ota_service = None
        if OTAService is not None:
            try:
                self.ota_service = OTAService(repo_path=self._repo_root)
            except Exception:
                self.logger.exception("No se pudo inicializar OTAService")
                self.ota_service = None

        self.root.after(300, self._update_weight_loop)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    # ------------------------------------------------------------------ Lifecycle
    def run(self) -> None:
        self.root.mainloop()

    def close(self) -> None:
        try:
            self._stop_bg_monitor()
            if self.hypo_timer:
                self.hypo_timer.close()
        except Exception:
            pass
        try:
            if self.wake:
                self.wake.stop()
        except Exception:
            pass
        try:
            self.topbar.set_mic_status(False)
        except Exception:
            pass
        try:
            if self.reader:
                self.reader.stop()
            if self.camera and hasattr(self.camera, "stop"):
                try:
                    self.camera.stop()  # type: ignore[attr-defined]
                except Exception:
                    pass
        finally:
            self.root.destroy()

    # ------------------------------------------------------------------ Navigation
    def show_screen(self, name: str) -> None:
        target = self.resolve_screen_name(name)
        screen = self.screens.get(target)
        if screen is None:
            self.logger.warning("Pantalla '%s' no encontrada", name)
            return
        if self.current_screen is screen:
            return
        previous = self.current_screen
        previous_name = self.current_screen_name
        self.logger.info("Mostrando pantalla %s", target)
        try:
            if previous is not None:
                try:
                    previous.on_hide()
                except Exception:
                    self.logger.debug("Error ocultando pantalla previa %s", previous_name, exc_info=True)
            self.transition_manager.current_screen = previous

            def _finalize() -> None:
                try:
                    self.current_screen = screen
                    self.current_screen_name = target
                    self._bind_screen_mascot(screen)
                    try:
                        screen.on_show()
                    except Exception as exc:
                        raise RuntimeError(f"on_show falló para {target}") from exc
                    self._speak_for_screen(target)
                    try:
                        self.topbar.set_active(target)
                    except Exception:
                        pass
                    try:
                        self.mascot_react("tap")
                    except Exception:
                        pass
                except Exception as exc:
                    self.logger.exception("Error activando pantalla %s", target)
                    self.current_screen = previous
                    self.current_screen_name = previous_name
                    self._handle_screen_failure(target, exc)

            transition = self._determine_transition(target)
            started = self.transition_manager.transition_to_screen(screen, transition, callback=_finalize)
            if not started:
                if previous is not None:
                    try:
                        previous.pack_forget()
                    except Exception:
                        pass
                screen.pack(fill=tk.BOTH, expand=True)
                _finalize()
        except Exception as exc:
            self.logger.exception("Error mostrando pantalla %s", target)
            self.current_screen = previous
            self.current_screen_name = previous_name
            self._handle_screen_failure(target, exc)

    def resolve_screen_name(self, name: str) -> str:
        return self._screen_canonical.get(name, name)

    def list_advanced_screens(self) -> Dict[str, str]:
        return dict(self._advanced_screens)

    def _notify_scale_fault(self) -> None:
        if self._scale_error_notified:
            return
        message = "Error de báscula"
        try:
            self.topbar.set_message(message)
        except Exception:
            pass
        try:
            self.show_mascot_message(message, kind="error", priority=7, icon="⚠️", ttl_ms=3600)
        except Exception:
            pass
        try:
            self.messenger.show(message, kind="error", priority=7, icon="⚠️")
        except Exception:
            pass
        self._scale_error_notified = True

    def _handle_scale_screen_error(self) -> None:
        self._notify_scale_fault()

        def _go_home() -> None:
            try:
                self.show_screen("home")
            except Exception:
                self.logger.error("No se pudo regresar a Home tras error en báscula", exc_info=True)

        try:
            self.root.after(250, _go_home)
        except Exception:
            _go_home()

    def _handle_screen_failure(self, target: str, exc: Exception | None = None) -> None:
        if target == "scale":
            self._handle_scale_screen_error()
            return
        label = self._screen_labels.get(target, target.title())
        message = f"Error al abrir {label}".strip()
        try:
            self.topbar.set_message(message)
        except Exception:
            pass
        try:
            self.messenger.show(message, kind="error", priority=7, icon="⚠️")
        except Exception:
            pass
        try:
            self.show_mascot_message(message, kind="error", priority=7, icon="⚠️", ttl_ms=3600)
        except Exception:
            pass
        if target != "home":
            self._schedule_home_fallback()

    def _schedule_home_fallback(self) -> None:
        if self.current_screen_name == "home":
            return

        def _go_home() -> None:
            if self.current_screen_name == "home":
                return
            try:
                self.show_screen("home")
            except Exception:
                self.logger.error("No se pudo regresar a Home tras error de pantalla", exc_info=True)

        try:
            self.root.after(250, _go_home)
        except Exception:
            _go_home()

    def _determine_transition(self, screen_name: str) -> TransitionType:
        pref = self._transition_pref
        if pref == "none":
            return TransitionType.NONE
        if pref == "scale":
            return TransitionType.SCALE
        if pref == "slide":
            return TransitionType.SLIDE_LEFT
        mapping = {
            "home": TransitionType.FADE,
            "scale": TransitionType.SLIDE_LEFT,
            "settings": TransitionType.SLIDE_RIGHT,
        }
        return mapping.get(screen_name, TransitionType.FADE)

    def _speak_for_screen(self, screen_name: str) -> None:
        if not self.voice or not self._voice_nav_enabled:
            return
        label = self._voice_screen_labels.get(screen_name) or self._screen_labels.get(screen_name)
        if not label:
            return
        try:
            self.voice.say(label)
        except Exception:
            self.logger.debug("No se pudo reproducir aviso de voz", exc_info=True)

    def _bind_screen_mascot(self, screen: tk.Frame) -> None:
        widget = getattr(screen, "mascota", None)
        if widget is None and hasattr(screen, "get_mascot_widget"):
            try:
                widget = screen.get_mascot_widget()  # type: ignore[attr-defined]
            except Exception:
                widget = None
        self._mascot_widget = widget
        self.mascot = widget if widget is not None else None  # type: ignore[assignment]

    def register_mascot_widget(self, widget: Optional[tk.Widget]) -> None:
        self._mascot_widget = widget
        self.mascot = widget if widget is not None else None  # type: ignore[assignment]

    def _get_mascot_widget(self) -> Optional[tk.Widget]:
        try:
            if self.mascot is not None and self.mascot.winfo_exists():
                return self.mascot
        except Exception:
            self.mascot = None
        try:
            if self._mascot_widget is not None and self._mascot_widget.winfo_exists():
                return self._mascot_widget
        except Exception:
            self._mascot_widget = None
        try:
            if hasattr(self.topbar, "mascot") and self.topbar.mascot.winfo_exists():
                return self.topbar.mascot
        except Exception:
            return None
        return None

    def mascot_react(self, kind: str) -> None:
        mapping = {
            "tap": "listen",
            "success": "think",
            "error": "error",
        }
        target = mapping.get(kind)
        if target:
            self.set_mascot_state(target)
        widget = self._get_mascot_widget()
        if widget and hasattr(widget, "react"):
            try:
                widget.react(kind)  # type: ignore[attr-defined]
            except Exception:
                pass

    def set_mascot_state(self, state: str) -> None:
        key = str(state or "").strip().lower()
        if key not in {"idle", "listen", "think", "error", "sleep"}:
            self.logger.debug("Mascot state desconocido: %s", state)
            return
        widget = self.mascot if getattr(self, "mascot", None) is not None else self._get_mascot_widget()
        if widget is not None and hasattr(widget, "set_state"):
            try:
                widget.set_state(key)  # type: ignore[attr-defined]
            except Exception:
                pass
        overlay = getattr(self, "_mascot_overlay_widget", None)
        if overlay is not None and hasattr(overlay, "set_state"):
            try:
                overlay.set_state(key)  # type: ignore[attr-defined]
            except Exception:
                pass
        self._mascot_state = key or "idle"
        if self._mascot_state == "sleep":
            self._cancel_mascot_sleep()
        else:
            self._schedule_mascot_sleep()

    def _bind_activity_events(self) -> None:
        def _activity(_event=None) -> None:
            self._on_user_activity()

        try:
            self.root.bind_all("<Any-KeyPress>", _activity, add=True)
            self.root.bind_all("<Button>", _activity, add=True)
            self.root.bind_all("<Motion>", _activity, add=True)
        except Exception:
            pass

    def _on_user_activity(self) -> None:
        if self._mascot_state == "sleep":
            self.set_mascot_state("idle")
        else:
            self._schedule_mascot_sleep()

    def _schedule_mascot_sleep(self) -> None:
        self._cancel_mascot_sleep()
        timeout = max(10, int(self._mascot_sleep_timeout))
        try:
            self._mascot_sleep_job = self.root.after(timeout * 1000, self._enter_mascot_sleep)
        except Exception:
            self._mascot_sleep_job = None

    def _cancel_mascot_sleep(self) -> None:
        if self._mascot_sleep_job:
            try:
                self.root.after_cancel(self._mascot_sleep_job)
            except Exception:
                pass
            self._mascot_sleep_job = None

    def _enter_mascot_sleep(self) -> None:
        self._mascot_sleep_job = None
        self.set_mascot_state("sleep")

    def toggle_mascot_overlay(self) -> None:
        window = getattr(self, "_mascot_overlay_window", None)
        try:
            if window is not None and window.winfo_exists():
                self._close_mascot_overlay()
                return
        except Exception:
            self._mascot_overlay_window = None
        self._open_mascot_overlay()

    def _open_mascot_overlay(self) -> None:
        try:
            if self._mascot_overlay_window is not None and self._mascot_overlay_window.winfo_exists():
                self._mascot_overlay_window.deiconify()
                self._mascot_overlay_window.lift()
                return
        except Exception:
            self._mascot_overlay_window = None
        from bascula.ui.mascot import MascotWidget  # lazy import to avoid circular deps

        window = tk.Toplevel(self.root)
        window.title("Mascota")
        window.configure(bg=COL_BG)
        try:
            window.attributes("-topmost", True)
        except tk.TclError:
            pass
        widget = MascotWidget(window, bg=COL_BG, max_width=280)
        widget.pack(expand=True, fill="both", padx=16, pady=16)
        try:
            widget.set_state(self._mascot_state)
            widget.blink(True)
            widget.pulse(True)
        except Exception:
            pass
        window.protocol("WM_DELETE_WINDOW", self._close_mascot_overlay)
        self._mascot_overlay_window = window
        self._mascot_overlay_widget = widget

    def _close_mascot_overlay(self) -> None:
        window = getattr(self, "_mascot_overlay_window", None)
        if window is not None:
            try:
                window.destroy()
            except Exception:
                pass
        self._mascot_overlay_window = None
        self._mascot_overlay_widget = None

    def _on_wake(self) -> None:
        def _respond() -> None:
            self.mascot_react("tap")
            self.show_mascot_message("Te escucho", kind="info", priority=5, icon="🎙️", ttl_ms=2600)

        try:
            self.root.after(0, _respond)
        except Exception:
            _respond()

    def handle_mascot_tap(self) -> None:
        self.mascot_react("tap")
        self.show_mascot_message("tap_greeting", kind="info", priority=1, icon="👋")

    def show_mascot_message(
        self,
        key: str,
        *args,
        kind: str = "info",
        priority: int = 0,
        icon: str = "💬",
        ttl_ms: int = 2200,
    ) -> None:
        try:
            text, action, anim = get_message(key, *args)
        except Exception:
            text, action, anim = str(key), None, None
        self.mascot_messenger.show(text, kind=kind, ttl_ms=ttl_ms, priority=priority, icon=icon, action=action, anim=anim)
        self.messenger.show(text, kind=kind, priority=priority, icon=icon)

    def _register_screen(
        self,
        screen_cls: Type[tk.Frame],
        *,
        key: Optional[str] = None,
        label: Optional[str] = None,
        aliases: Iterable[str] = (),
        advanced: bool = False,
    ) -> None:
        name = key or getattr(screen_cls, "name", None)
        if not name:
            self.logger.warning("Pantalla %s sin nombre; ignorando", screen_cls.__name__)
            return
        try:
            screen = screen_cls(self.container, self)
        except Exception as exc:  # pragma: no cover - failsafe for optional screens
            self.logger.exception(
                "No se pudo inicializar la pantalla %s", screen_cls.__name__, exc_info=exc
            )
            return
        aliases = tuple(a for a in aliases if a)
        display = label or getattr(screen, "title", getattr(screen_cls, "title", name.title()))
        keys = {name, *aliases}
        for entry in keys:
            self.screens[entry] = screen
            self._screen_canonical[entry] = name
            self._screen_labels[entry] = display
        if advanced:
            self._advanced_screens[name] = display

    def _try_register(
        self,
        key: str,
        module_name: str,
        class_name: str,
        *,
        label: Optional[str] = None,
        advanced: bool = True,
    ) -> bool:
        try:
            module = import_module(module_name)
        except Exception as exc:
            self.logger.warning(
                "[warn] No se pudo importar el módulo opcional %s: %s", module_name, exc
            )
            return False
        screen_cls = getattr(module, class_name, None)
        if screen_cls is None:
            self.logger.warning(
                "[warn] %s no define %s; omitiendo pantalla opcional", module_name, class_name
            )
            return False
        aliases: Sequence[str] = ()
        alias = getattr(screen_cls, "name", None)
        if alias and alias != key:
            aliases = (alias,)
        self._register_screen(screen_cls, key=key, label=label, aliases=aliases, advanced=advanced)
        return True

    # ------------------------------------------------------------------ Overlay helpers
    def _disable_recipe_button(self) -> None:
        try:
            if hasattr(self.topbar, "disable_recipes_entry"):
                self.topbar.disable_recipes_entry()
        except Exception:
            pass

    def _ensure_recipe_overlay(self) -> Optional["RecipeOverlay"]:
        if self._recipe_import_failed:
            return None
        overlay = self._recipe_overlay
        if overlay is None or not getattr(overlay, "winfo_exists", lambda: False)():
            try:
                from bascula.ui.overlay_recipe import RecipeOverlay as _RecipeOverlay
            except Exception:
                self.logger.warning("Modo recetas no disponible (import)", exc_info=True)
                self._recipe_import_failed = True
                self._disable_recipe_button()
                return None
            try:
                overlay = _RecipeOverlay(self.root, self)
            except Exception:
                self.logger.exception("No se pudo crear el modo recetas")
                overlay = None
            self._recipe_overlay = overlay
            if overlay is None:
                self._recipe_import_failed = True
                self._disable_recipe_button()
        return overlay

    def _ensure_timer_overlay(self) -> Optional["TimerOverlay"]:
        if self._timer_import_failed:
            return None
        overlay = self._timer_overlay
        if overlay is None or not getattr(overlay, "winfo_exists", lambda: False)():
            try:
                from bascula.ui.overlay_timer import TimerOverlay as _TimerOverlay
            except Exception:
                self.logger.warning("Temporizador rápido no disponible (import)", exc_info=True)
                self._timer_import_failed = True
                return None
            try:
                overlay = _TimerOverlay(self.root, self)
            except Exception:
                self.logger.exception("No se pudo crear el temporizador rápido")
                overlay = None
            self._timer_overlay = overlay
            if overlay is None:
                self._timer_import_failed = True
        return overlay

    def _ensure_favorites_overlay(self) -> Optional["FavoritesOverlay"]:
        if self._favorites_import_failed:
            return None
        overlay = self._favorites_overlay
        if overlay is None or not getattr(overlay, "winfo_exists", lambda: False)():
            try:
                from bascula.ui.overlay_favorites import FavoritesOverlay as _FavoritesOverlay
            except Exception:
                self.logger.warning("Overlay de favoritos no disponible (import)", exc_info=True)
                self._favorites_import_failed = True
                return None
            try:
                overlay = _FavoritesOverlay(self.root, self, on_add_item=self._on_favorite_selected)
            except Exception:
                self.logger.exception("No se pudo crear el overlay de favoritos")
                overlay = None
            self._favorites_overlay = overlay
            if overlay is None:
                self._favorites_import_failed = True
        return overlay

    def open_recipes(self) -> None:
        overlay = self._ensure_recipe_overlay()
        if overlay is None:
            self.show_mascot_message("Recetas no disponibles", kind="error", priority=6, icon="⚠️")
            return
        try:
            overlay.show()
        except Exception:
            self.logger.exception("No se pudo abrir el modo recetas")
            self.show_mascot_message("Recetas no disponibles", kind="error", priority=6, icon="⚠️")
            return
        try:
            self.mascot_react("tap")
        except Exception:
            pass
        try:
            self.show_mascot_message("Modo recetas", kind="info", priority=3, icon="🍳")
        except Exception:
            pass

    def open_timer_overlay(self, preset: Optional[int] = None) -> None:
        overlay = self._ensure_timer_overlay()
        if overlay is None:
            self.show_mascot_message("Temporizador no disponible", kind="error", priority=5, icon="⚠️")
            return
        try:
            overlay.show()
            if preset:
                overlay.start(int(preset))
        except Exception:
            self.logger.exception("No se pudo mostrar el temporizador")
            self.show_mascot_message("Temporizador no disponible", kind="error", priority=5, icon="⚠️")
            return
        try:
            self.mascot_react("tap")
        except Exception:
            pass
        try:
            self.show_mascot_message("Temporizador listo", kind="info", priority=2, icon="⏱")
        except Exception:
            pass

    def open_favorites(self) -> None:
        overlay = self._ensure_favorites_overlay()
        if overlay is None:
            self.show_mascot_message("Favoritos no disponibles", kind="warning", priority=3, icon="ℹ️")
            return
        try:
            overlay.show()
        except Exception:
            self.logger.exception("No se pudo abrir favoritos")
            self.show_mascot_message("Favoritos no disponibles", kind="warning", priority=3, icon="ℹ️")
            return
        try:
            self.mascot_react("tap")
        except Exception:
            pass

    def _on_favorite_selected(self, item: Any) -> None:
        name = None
        try:
            name = getattr(item, "name", None)
        except Exception:
            name = None
        if not name and isinstance(item, dict):
            name = str(item.get("name") or item.get("id") or "" ).strip()
        name = name or str(item or "").strip()
        macros: dict[str, float] = {}
        for key in ("kcal", "carbs", "protein", "fat"):
            value = None
            if isinstance(item, dict):
                value = item.get(key)
                if value is None and isinstance(item.get("macros_100"), dict):
                    value = item["macros_100"].get(key)
            else:
                value = getattr(item, key, None)
            try:
                macros[key] = float(value) if value is not None else 0.0
            except Exception:
                macros[key] = 0.0
        try:
            added = self.add_meal_item(name, macros_100=macros, source="favorite") if name else None
        except Exception:
            self.logger.exception("Error añadiendo favorito %s", name or "(sin nombre)")
            added = None
        if added:
            try:
                self.mascot_react("success")
            except Exception:
                pass
            message = f"Añadido {name}" if name else "Añadido"
            try:
                self.show_mascot_message(message, kind="success", priority=4, icon="⭐", ttl_ms=2600)
            except Exception:
                pass
            try:
                self.messenger.show(message, kind="info", priority=3, icon="⭐")
            except Exception:
                pass
            try:
                self.topbar.set_message(message)
            except Exception:
                pass
        else:
            warn = f"No se pudo añadir {name}" if name else "No se pudo añadir"
            try:
                self.show_mascot_message(warn, kind="warning", priority=2, icon="ℹ️")
            except Exception:
                pass

    # ------------------------------------------------------------------ Services API
    def get_cfg(self) -> dict:
        return self.cfg

    def save_cfg(self) -> None:
        previous_mode = self.diabetes_mode
        save_config(self.cfg)
        new_theme = self.cfg.get("ui_theme", getattr(self, "active_theme", "modern"))
        try:
            apply_theme(self.root, new_theme)
            refresh_theme_cache()
            self.active_theme = new_theme
            self.mascot_messenger.pal.update({
                "COL_CARD": COL_CARD,
                "COL_TEXT": COL_TEXT,
                "COL_ACCENT": COL_ACCENT,
            })
            try:
                if hasattr(self.topbar, "mascot"):
                    self.topbar.mascot.refresh()
            except Exception:
                pass
        except Exception:
            self.logger.exception("No se pudo aplicar el tema tras guardar la configuración")
        self._voice_nav_enabled = bool(self.cfg.get("voice_prompts", False))
        new_mode = bool(self.cfg.get("diabetic_mode", False))
        if new_mode != previous_mode:
            self.diabetes_mode = new_mode
            if new_mode:
                self._start_bg_monitor()
            else:
                self._stop_bg_monitor()

    def toggle_sound(self) -> None:
        enabled = not bool(self.cfg.get("sound_enabled", True))
        self.cfg["sound_enabled"] = enabled
        self.save_cfg()
        if self.audio:
            try:
                self.audio.set_enabled(enabled)  # type: ignore[attr-defined]
            except Exception:
                pass

    def get_audio(self):  # pragma: no cover - convenience hook for settings modules
        return self.audio

    def get_reader(self) -> Optional[ScaleService]:
        return self.reader

    def get_tare(self) -> TareManager:
        return self.tare

    def get_latest_weight(self) -> float:
        raw = self.reader.get_weight() if self.reader else 0.0
        smooth = self._smoothing.add(raw)
        return self.tare.compute_net(smooth)

    def _start_bg_monitor(self) -> None:
        if self.bg_monitor is not None:
            return
        try:
            self.bg_monitor = BgMonitor(self)
            self.bg_monitor.start()
            self.logger.info("Monitor de glucosa iniciado")
        except Exception:
            self.logger.exception("No se pudo iniciar el monitor de glucosa")
            self.bg_monitor = None

    def _stop_bg_monitor(self) -> None:
        if self.bg_monitor is not None:
            try:
                self.bg_monitor.stop()
            except Exception:
                pass
            self.bg_monitor = None
        self.state.clear_hypo_flow()

    # ------------------------------------------------------------------ Actions
    def perform_tare(self) -> None:
        raw = self.reader.get_weight() if self.reader else 0.0
        self.tare.set_tare(raw)
        self._last_captured = 0.0
        self.show_mascot_message("tara_applied", kind="success", priority=4, icon="⚖️")

    def perform_zero(self) -> None:
        self.tare.clear_tare()
        self._last_captured = 0.0
        self.show_mascot_message("zero_applied", kind="info", priority=3, icon="🧮")

    def capture_weight(self) -> None:
        weight = self.get_latest_weight()
        if weight <= 0:
            self.messenger.show("No hay peso estable para capturar", kind="warning", icon="ℹ️")
            return
        self._append_history(weight, manual=True)
        self.event_bus.publish("WEIGHT_CAPTURED", weight)
        self.show_mascot_message("auto_captured", weight, kind="success", priority=5, icon="📸")

    def open_scanner(self) -> None:
        try:
            from bascula.ui.overlay_scanner import ScannerOverlay
        except Exception:
            self.logger.exception("Overlay de escaneo no disponible")
            self.show_mascot_message("Escáner no disponible", kind="error", priority=6, icon="⚠️")
            return

        overlay = self._scanner_overlay
        if overlay is None or not getattr(overlay, "winfo_exists", lambda: False)():
            try:
                overlay = ScannerOverlay(
                    self.root,
                    self,
                    on_result=self._on_scanner_detected,
                    on_timeout=self._on_scanner_timeout,
                )
                self._scanner_overlay = overlay
            except Exception:
                self.logger.exception("No se pudo crear el overlay del escáner")
                self.show_mascot_message("Escáner no disponible", kind="error", priority=6, icon="⚠️")
                return
        try:
            overlay.show()
            self.event_bus.publish("SCANNER_OPEN", None)
        except Exception:
            self.logger.exception("No se pudo mostrar el escáner")
            self.show_mascot_message("Escáner no disponible", kind="error", priority=6, icon="⚠️")
            return
        self.mascot_react("tap")

    def _on_scanner_detected(self, code: str) -> None:
        def handler() -> None:
            payload = (code or "").strip()
            if payload:
                self.mascot_react("success")
                self.show_mascot_message("scanner_detected", kind="success", priority=6, icon="✅")
                self._register_barcode_capture(payload)
            else:
                self._vision_suggest_from_snapshot()

        try:
            self.root.after(0, handler)
        except Exception:
            handler()

    def _on_scanner_timeout(self) -> None:
        def handler() -> None:
            self.show_mascot_message("No se detectó código", kind="warning", priority=3, icon="⌛")
            self._vision_suggest_from_snapshot()

        try:
            self.root.after(0, handler)
        except Exception:
            handler()

    def _register_barcode_capture(self, code: str) -> None:
        label = code
        stored = False
        product = None
        entry = {}
        try:
            from bascula.services.off_lookup import fetch_off
        except Exception:
            fetch_off = None  # type: ignore
        if fetch_off:
            try:
                product = fetch_off(code)
            except Exception:
                product = None
        if product:
            try:
                entry = upsert_from_off(product) or {}
                label = entry.get("name") or label
                stored = True
            except Exception:
                label = (product.get("product_name") if isinstance(product, dict) else None) or label
                stored = False
        macros = {}
        if isinstance(entry, dict):
            macros = entry.get("macros_100") or {}
        payload = {
            "barcode": code,
            "name": label,
            "source": "off" if stored else "scan",
        }
        self._append_food_event(payload)
        if label:
            metadata = {"barcode": code}
            added = self.add_meal_item(label, macros_100=macros, source="barcode", metadata=metadata)
            if added:
                try:
                    self.topbar.set_message(f"Añadido {label}")
                except Exception:
                    pass
        try:
            self.event_bus.publish("SCANNER_DETECTED", code)
        except Exception:
            pass
        self.messenger.show(f"Guardado {label}", kind="success", priority=6, icon="🍏")
        try:
            self.topbar.set_message(f"Guardado {label}")
        except Exception:
            pass

    def _vision_suggest_from_snapshot(self) -> None:
        cam = getattr(self, "camera", None)
        if not cam or not getattr(cam, "available", lambda: False)():
            self.show_mascot_message("Cámara no disponible", kind="warning", priority=2, icon="📷")
            self.mascot_react("error")
            return
        frame = None
        try:
            frame = cam.grab_frame()
        except Exception:
            frame = None
        if frame is None:
            self.show_mascot_message("Sin imagen de cámara", kind="warning", priority=2, icon="📷")
            return
        vision = getattr(self, "vision_service", None)
        if vision is None:
            self.show_mascot_message("Activa visión en Ajustes", kind="warning", priority=2, icon="🧠")
            return
        try:
            result = vision.classify_image(frame)
        except Exception:
            result = None
        if not result:
            self.show_mascot_message("No se reconoció el alimento", kind="warning", priority=2, icon="❓")
            self.mascot_react("error")
            return
        label, confidence = result
        data = {"name": label, "confidence": float(confidence), "source": "vision"}
        self._append_food_event(data)
        added = self.add_meal_item(label, source="vision", metadata={"confidence": float(confidence)})
        if added:
            self.show_mascot_message(f"Añadido {label}", kind="info", priority=4, icon="🍽", ttl_ms=3200)
        else:
            self.show_mascot_message(f"Sugerencia: {label}", kind="info", priority=4, icon="🍽", ttl_ms=3200)
        self.mascot_react("success")

    def _append_food_event(self, data: dict) -> None:
        path = Path.home() / ".config" / "bascula" / "foods.jsonl"
        body = dict(data)
        body.setdefault("ts", time.time())
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(body, ensure_ascii=False) + "\n")
        except Exception:
            self.logger.debug("No se pudo escribir foods.jsonl", exc_info=True)

    # ------------------------------------------------------------------ Meal flow
    def reset_meal(self) -> None:
        self.meal_items.clear()
        self._meal_started_ts = time.time()
        self._last_meal_weight = self._capture_current_weight()
        self._notify_meal_change("reset")

    def _notify_meal_change(self, reason: str, item: Optional[dict] = None) -> None:
        payload = {
            "items": [dict(entry) for entry in self.meal_items],
            "totals": self._compute_meal_totals(),
            "reason": reason,
        }
        if item is not None:
            payload["item"] = dict(item)
        self.state.latest_meal = payload
        try:
            self.event_bus.publish("meal_updated", payload)
        except Exception:
            pass

    def _compute_meal_totals(self) -> dict:
        totals = {"grams": 0.0, "carbs": 0.0, "kcal": 0.0, "gi": None}
        ig_sum = 0.0
        ig_weight = 0.0
        for item in self.meal_items:
            grams = float(item.get("grams") or 0.0)
            carbs = float(item.get("carbs") or 0.0)
            kcal = float(item.get("kcal") or 0.0)
            totals["grams"] += grams
            totals["carbs"] += carbs
            totals["kcal"] += kcal
            gi = item.get("ig")
            if isinstance(gi, (int, float)) and gi > 0:
                ig_sum += gi * grams
                ig_weight += grams
        if ig_weight > 0:
            totals["gi"] = round(ig_sum / ig_weight)
        return totals

    def get_meal_totals(self) -> dict:
        return self._compute_meal_totals()

    def _capture_current_weight(self) -> float:
        try:
            return max(0.0, float(self.get_latest_weight()))
        except Exception:
            return 0.0

    def _next_item_weight(self, override: Optional[float] = None) -> float:
        if override is not None:
            try:
                value = max(0.0, float(override))
                self._last_meal_weight = self._capture_current_weight()
                return value
            except Exception:
                pass
        current = self._capture_current_weight()
        delta = current - self._last_meal_weight
        if delta <= 0 and current > 0:
            delta = current
        self._last_meal_weight = current
        return max(0.0, round(delta, 1))

    def add_meal_item(
        self,
        name: str,
        *,
        macros_100: Optional[dict] = None,
        grams: Optional[float] = None,
        source: str = "manual",
        ig_value: Optional[float] = None,
        metadata: Optional[dict] = None,
    ) -> Optional[dict]:
        name = (name or "").strip()
        if not name:
            return None
        weight = self._next_item_weight(grams)
        if weight <= 0:
            weight = self._capture_current_weight()
        if weight <= 0:
            return None
        macros = macros_100 or {}
        factor = weight / 100.0 if weight else 0.0
        carbs = float(macros.get("carbs") or 0.0) * factor
        kcal = float(macros.get("kcal") or 0.0) * factor
        entry = {
            "name": name,
            "grams": round(weight, 1),
            "carbs": round(carbs, 1),
            "kcal": round(kcal, 1),
            "source": source,
            "metadata": metadata or {},
        }
        if ig_value is None:
            ig_value, ig_source = self.lookup_gi(name)
        else:
            ig_source = "manual"
        try:
            ig_num = float(ig_value)
            entry["ig"] = round(ig_num)
            entry["ig_source"] = ig_source
        except Exception:
            entry["ig"] = "n/d"
            if ig_value:
                entry["ig_source"] = ig_source
        self.meal_items.append(entry)
        self._notify_meal_change("add", entry)
        return entry

    def remove_last_meal_item(self) -> None:
        if not self.meal_items:
            return
        removed = self.meal_items.pop()
        self._notify_meal_change("remove", removed)

    def save_current_meal(self) -> Optional[dict]:
        if not self.meal_items:
            self.show_mascot_message("No hay alimentos en el plato", kind="warning", priority=3, icon="ℹ️")
            return None
        payload = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "items": [dict(item) for item in self.meal_items],
            "totals": self._compute_meal_totals(),
        }
        self._persist_meal(payload)
        self.show_mascot_message("Guardado", kind="success", priority=6, icon="🍽", ttl_ms=2800)
        self.mascot_react("success")
        self._maybe_notify_bolus(payload)
        return payload

    def _persist_meal(self, payload: dict) -> None:
        path = Path.home() / ".config" / "bascula" / "meals.jsonl"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
        except Exception:
            self.logger.debug("No se pudo escribir meals.jsonl", exc_info=True)

    def _maybe_notify_bolus(self, meal_payload: dict) -> None:
        cfg = self.get_cfg()
        target = cfg.get("target_bg_mgdl")
        ratio = cfg.get("carb_ratio_g_per_u")
        isf = cfg.get("isf_mgdl_per_u")
        if not (self.diabetes_mode and self._last_bg and target and ratio and isf):
            if self.diabetes_mode:
                self.show_mascot_message(
                    "Configura objetivo, ISF y ratio en Ajustes",
                    kind="warning",
                    priority=5,
                    icon="⚙️",
                    ttl_ms=3600,
                )
            return
        carbs = float(meal_payload.get("totals", {}).get("carbs") or 0.0)
        if carbs <= 0:
            return
        try:
            result = calc_bolus(
                grams_carbs=carbs,
                target_bg=int(target),
                current_bg=int(self._last_bg),
                isf=float(isf),
                ratio=float(ratio),
            )
        except Exception:
            self.logger.exception("Error calculando bolo informativo")
            return
        payload = {
            "carbs": round(carbs, 1),
            "units": round(result.bolus, 2),
            "current_bg": self._last_bg,
            "target": target,
            "window_min": int(self.cfg.get("bolus_window_min", 15)),
            "peak_time": getattr(result, "peak_time_min", 60),
        }
        self.show_mascot_message(
            "Recuerda tu bolo y la ventana de inyección.",
            kind="info",
            priority=7,
            icon="💉",
            ttl_ms=4200,
        )
        if self.voice is not None:
            try:
                self.voice.say("Recuerda tu bolo y la ventana de inyección.")
            except Exception:
                pass
        try:
            self.event_bus.publish("bolus_recommendation", payload)
        except Exception:
            pass

    def lookup_gi(self, name: str) -> tuple[str, str]:
        raw_key = (name or "").strip().lower()
        if not raw_key:
            return "n/d", ""
        norm = unicodedata.normalize("NFKD", raw_key)
        key = "".join(ch for ch in norm if not unicodedata.combining(ch))
        if key in self._gi_cache:
            val, source = self._gi_cache[key]
            return val, source
        base = self._gi_table.get(key)
        if base is not None:
            result = (str(base), "tabla")
            self._gi_cache[key] = result
            return result
        for candidate, value in self._gi_table.items():
            if candidate in key or candidate in raw_key:
                result = (str(value), "tabla")
                self._gi_cache[key] = result
                return result
        if self.llm_client is not None:
            try:
                prompt = (
                    "Proporciona únicamente el índice glucémico aproximado del alimento indicado en números. "
                    f"Alimento: {name}."
                )
                response = self.llm_client.generate(prompt)
                if response:
                    digits = "".join(ch for ch in response if ch.isdigit())
                    if digits:
                        self._gi_cache[key] = (digits, "LLM")
                        return digits, "LLM"
            except Exception:
                self.logger.debug("LLM sin respuesta para IG de %s", name, exc_info=True)
        return "n/d", ""

    # ------------------------------------------------------------------ Nightscout / BG
    def on_bg_update(self, value: int, direction: str = "") -> None:
        self._last_bg = int(value)
        self._last_bg_direction = direction
        timestamp = getattr(self.bg_monitor, "timestamp", None)
        self._last_bg_ts = timestamp
        self._bg_pred_15 = getattr(self.bg_monitor, "bg_pred_15", None)
        self._bg_pred_30 = getattr(self.bg_monitor, "bg_pred_30", None)
        state = self.state.update_bg(value, direction, timestamp)
        if self.diabetes_mode and value < 70:
            self._show_hypo_prompt(value)
        elif state.get("normalized") and self.hypo_timer and self.hypo_timer.is_running():
            self.on_hypo_timer_finished()

    def on_bg_error(self, message: str) -> None:
        self.logger.warning("Nightscout: %s", message)
        self.mascot_react("error")
        text = (message or "Error Nightscout").strip()
        self.show_mascot_message(text, kind="error", priority=7, icon="⚠️", ttl_ms=3600)

    def _show_hypo_prompt(self, bg_value: int) -> None:
        if self.state.hypo_modal_open or (self.hypo_timer and self.hypo_timer.is_running()):
            return
        self.state.hypo_modal_open = True
        self.mascot_react("error")
        self.show_mascot_message("hypo_alert", bg_value, kind="warning", priority=8, icon="🩸", ttl_ms=4200)
        overlay = self.hypo_overlay
        if overlay is None:
            self.logger.warning("Overlay de hipoglucemia no disponible")
            self.state.hypo_modal_open = False
            return
        try:
            overlay.present(bg_value)
        except Exception:
            self.state.hypo_modal_open = False

    def start_hypo_timer(self) -> None:
        timer = self.hypo_timer
        if timer and timer.is_running():
            self.show_mascot_message("hypo_timer_started", kind="info", priority=6, icon="⏱", ttl_ms=2400)
            return
        self.state.hypo_modal_open = False
        self._hypo_timer_started_ts = time.time()
        self.mascot_react("error")
        self.show_mascot_message("hypo_timer_started", kind="warning", priority=8, icon="⏱", ttl_ms=3600)
        if self.voice is not None:
            try:
                self.voice.say("Hipoglucemia detectada. Iniciando temporizador de quince minutos.")
            except Exception:
                self.logger.debug("No se pudo reproducir aviso de voz", exc_info=True)
        if timer is None:
            self.logger.warning("Temporizador 15/15 no disponible")
            return
        try:
            timer.open(duration=15 * 60)
        except Exception:
            self.logger.exception("No se pudo abrir el temporizador 15/15")

    def on_hypo_overlay_closed(self) -> None:
        self.state.hypo_modal_open = False

    def on_hypo_timer_started(self) -> None:
        self._hypo_timer_started_ts = time.time()

    def on_hypo_timer_cancelled(self) -> None:
        self._hypo_timer_started_ts = None
        self.state.clear_hypo_flow()

    def on_hypo_timer_finished(self) -> None:
        timer = self.hypo_timer
        if self._hypo_timer_started_ts is None and (not timer or not timer.is_running()):
            return
        self._hypo_timer_started_ts = None
        self.state.clear_hypo_flow()
        self.show_mascot_message("hypo_timer_finished", kind="success", priority=9, icon="✅", ttl_ms=4200)
        self.mascot_react("success")

    def show_history(self) -> None:  # pragma: no cover - small popup
        popup = tk.Toplevel(self.root)
        popup.title("Historial de pesajes")
        popup.geometry("360x400")
        popup.configure(bg=COL_BG)
        lb = tk.Listbox(popup, bg=COL_BG, fg="white", highlightthickness=0)
        lb.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        for entry in self.weight_history:
            lb.insert(tk.END, f"{entry['ts'].strftime('%d/%m %H:%M')} · {entry['value']}")

    def set_focus_mode(self, enabled: bool) -> None:  # pragma: no cover - placeholder hook
        self.cfg["focus_mode"] = bool(enabled)

    def restart_ui(self) -> None:
        try:
            self.root.destroy()
            os.execl(sys.executable, sys.executable, *sys.argv)
        except Exception:
            self.logger.exception("No se pudo reiniciar la interfaz")

    def trigger_ota_update(self) -> None:
        if self.ota_service is None:
            self.show_mascot_message("ota_failed", "Servicio no disponible", kind="error", icon="⚠️")
            return
        started = self.ota_service.trigger_update(callback=self._on_ota_result)
        if not started:
            self.show_mascot_message("ota_started", kind="info", priority=4, icon="⏳")
            return
        self.show_mascot_message("ota_started", kind="info", priority=5, icon="⬇️", ttl_ms=3600)

    def _on_ota_result(self, result: dict) -> None:
        def handler() -> None:
            if result.get("success"):
                ver = result.get("version", "")
                self.show_mascot_message("ota_done", ver, kind="success", priority=9, icon="✅", ttl_ms=4200)
                self.root.after(2500, self.restart_ui)
            else:
                err = result.get("error") or "Error desconocido"
                self.show_mascot_message("ota_failed", err, kind="error", priority=9, icon="⚠️", ttl_ms=4800)

        try:
            self.root.after(0, handler)
        except Exception:
            handler()

    # ------------------------------------------------------------------ Internal loops
    def _update_weight_loop(self) -> None:
        error = False
        try:
            weight = self.get_latest_weight()
        except Exception:
            self.logger.warning("Lectura de báscula falló", exc_info=True)
            weight = 0.0
            error = True
        decimals = max(0, int(self.cfg.get("decimals", 0)))
        unit = str(self.cfg.get("unit", "g"))
        formatted = f"{weight:.{decimals}f} {unit}"
        try:
            stable = bool(self.reader.is_stable()) if self.reader else False
        except Exception:
            self.logger.warning("No se pudo consultar estabilidad de báscula", exc_info=True)
            stable = False
            error = True

        self.weight_text.set(formatted)
        self.stability_text.set("Estable" if stable else "Midiendo…")
        try:
            self.topbar.update_weight(formatted, stable)
        except Exception:
            pass

        if error:
            self._notify_scale_fault()
        elif self._scale_error_notified:
            self._scale_error_notified = False
            try:
                self.topbar.clear_message()
            except Exception:
                pass

        if stable and weight > 0:
            if abs(weight - self._last_captured) >= self._capture_min_delta:
                self._append_history(weight)
                self._last_captured = weight

        self.root.after(250, self._update_weight_loop)

    def _append_history(self, weight: float, manual: bool = False) -> None:
        from datetime import datetime

        formatted = f"{weight:.{max(0, int(self.cfg.get('decimals', 0)))}f} {self.cfg.get('unit', 'g')}"
        entry = {"ts": datetime.now(), "value": formatted, "manual": manual}
        self.weight_history.append(entry)
        self.weight_history = self.weight_history[-20:]
        if self.current_screen and hasattr(self.current_screen, "_refresh_history"):
            try:
                self.current_screen._refresh_history()  # type: ignore[attr-defined]
            except Exception:
                pass
        if not manual:
            try:
                self.show_mascot_message("auto_captured", weight, kind="info", priority=2, icon="📥")
            except Exception:
                pass

    def _resolve_repo_root(self) -> Path:
        path = Path(__file__).resolve()
        for candidate in [path, *path.parents]:
            if (candidate / ".git").exists():
                return candidate
        return path.parent

    # ------------------------------------------------------------------ Mini web helpers
    def get_status_snapshot(self) -> dict:
        return {
            "screen": self.current_screen_name,
            "weight": self.weight_text.get(),
            "stable": bool(self.reader.is_stable()) if self.reader else False,
            "last_bg": self._last_bg,
            "bg_direction": self._last_bg_direction,
            "bg_timestamp": self._last_bg_ts,
            "bg_pred_15": self._bg_pred_15,
            "bg_pred_30": self._bg_pred_30,
            "diabetes_mode": self.diabetes_mode,
            "hypo_timer_active": self.hypo_timer.is_running() if self.hypo_timer else False,
            "hypo_timer_remaining": self.hypo_timer.remaining_seconds() if self.hypo_timer else 0,
            "meal": self.state.latest_meal if hasattr(self.state, "latest_meal") else {
                "totals": self._compute_meal_totals(),
                "items": [dict(item) for item in self.meal_items],
            },
        }

    def get_settings_snapshot(self) -> dict:
        ns = self._read_nightscout_cfg()
        cfg = self.get_cfg()
        return {
            "ui_theme": cfg.get("ui_theme", self.active_theme),
            "diabetic_mode": self.diabetes_mode,
            "nightscout": ns,
        }

    def update_settings_from_dict(self, data: dict) -> tuple[bool, str]:
        try:
            cfg_changed = False
            cfg = self.get_cfg()
            if "ui_theme" in data:
                theme = str(data.get("ui_theme") or "").strip() or cfg.get("ui_theme", self.active_theme)
                cfg["ui_theme"] = theme
                cfg_changed = True
            if "diabetic_mode" in data:
                cfg["diabetic_mode"] = bool(data.get("diabetic_mode"))
                cfg_changed = True
            if "bolus_window_min" in data:
                try:
                    cfg["bolus_window_min"] = max(1, int(data.get("bolus_window_min")))
                    cfg_changed = True
                except Exception:
                    pass
            ns_data = data.get("nightscout")
            if isinstance(ns_data, dict):
                url = str(ns_data.get("url") or "").strip()
                token = str(ns_data.get("token") or "").strip()
                self._write_nightscout_cfg(url, token)
            if cfg_changed:
                self.save_cfg()
            return True, "ok"
        except Exception as exc:
            self.logger.exception("Error actualizando ajustes desde miniweb")
            return False, str(exc)

    def _nightscout_file(self) -> Path:
        cfg_dir_env = os.environ.get("BASCULA_CFG_DIR", "").strip()
        cfg_dir = Path(cfg_dir_env) if cfg_dir_env else (Path.home() / ".config" / "bascula")
        cfg_dir.mkdir(parents=True, exist_ok=True)
        return cfg_dir / "nightscout.json"

    def _read_nightscout_cfg(self) -> dict:
        path = self._nightscout_file()
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
        return {"url": "", "token": ""}

    def _write_nightscout_cfg(self, url: str, token: str) -> None:
        path = self._nightscout_file()
        data = {"url": url.strip(), "token": token.strip()}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except Exception:
            pass


# Backwards compatibility export -------------------------------------------------
BasculaApp = BasculaAppTk


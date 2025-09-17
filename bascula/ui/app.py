"""High level Tkinter application used by the Báscula Cam kiosk."""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from importlib import import_module
import tkinter as tk
from pathlib import Path
from typing import Dict, Iterable, Optional, Type

from bascula.config.theme import apply_theme
from bascula.state import AppState
from bascula.domain.foods import upsert_from_off
from bascula.services.bg_monitor import BgMonitor
from bascula.services.event_bus import EventBus
from bascula.services.scale import ScaleService
from bascula.services.tare_manager import TareManager
from bascula.utils import MovingAverage, load_config, save_config
from bascula.ui.mascot_messages import MascotMessenger, get_message
from bascula.ui.overlay_timer import HypoOverlay, TimerPopup
from bascula.ui.transitions import TransitionManager, TransitionType
from bascula.ui.widgets import TopBar, COL_BG, COL_CARD, COL_ACCENT, COL_TEXT, refresh_theme_cache
from bascula.ui.screens import HomeScreen, ScaleScreen, SettingsScreen

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
        self._repo_root = self._resolve_repo_root()
        self.diabetes_mode = bool(self.cfg.get("diabetic_mode", False))
        self._last_bg: Optional[int] = None
        self._last_bg_direction: str = ""
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
        self._voice_nav_enabled = bool(self.cfg.get("voice_prompts", False))
        self._voice_screen_labels: Dict[str, str] = {
            "home": "Inicio",
            "scale": "Pesaje",
            "settings": "Ajustes",
        }
        self._scanner_overlay = None

        palette = {"COL_CARD": COL_CARD, "COL_TEXT": COL_TEXT, "COL_ACCENT": COL_ACCENT}
        self.mascot_messenger = MascotMessenger(self._get_mascot_widget, lambda: self.topbar, palette)

        # Screen registry ---------------------------------------------------
        self.screens: Dict[str, tk.Frame] = {}
        self._screen_canonical: Dict[str, str] = {}
        self._screen_labels: Dict[str, str] = {}
        self._advanced_screens: Dict[str, str] = {}

        base_screens: Iterable[tuple[str, Type[tk.Frame], str, tuple[str, ...]]] = (
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
            ("focus", "Enfoque", "bascula.ui.focus_screen", "FocusScreen"),
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
            self._register_optional_screen(key, module_name, class_name, label=label)

        try:
            self.topbar.filter_missing(self.screens)
        except Exception:
            pass

        self.show_screen("home")

        # Services ------------------------------------------------------------------
        self.reader: Optional[ScaleService] = None
        self.tare = TareManager(calib_factor=float(self.cfg.get("calib_factor", 1.0)))
        self._smoothing = MovingAverage(size=max(1, int(self.cfg.get("smoothing", 5))))
        self._last_captured = 0.0
        self._capture_min_delta = float(self.cfg.get("auto_capture_min_delta_g", 8))

        try:
            self.reader = ScaleService(
                port=str(self.cfg.get("port", "/dev/serial0")),
                baud=int(self.cfg.get("baud", 115200)),
                logger=self.logger,
                fail_fast=False,
            )
            self.reader.start()
        except Exception:
            self.logger.exception("No se pudo iniciar el lector de la báscula")
            self.reader = None

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

        self.hypo_overlay = HypoOverlay(self.root, self)
        self.hypo_timer = TimerPopup(self.root, self, duration_s=15 * 60)
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
        if previous is not None:
            try:
                previous.on_hide()
            except Exception:
                pass
        self.transition_manager.current_screen = previous

        def _finalize() -> None:
            self.current_screen = screen
            self.current_screen_name = target
            self._bind_screen_mascot(screen)
            try:
                screen.on_show()
            except Exception:
                pass
            self._speak_for_screen(target)
            try:
                self.topbar.set_active(target)
            except Exception:
                pass

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

    def resolve_screen_name(self, name: str) -> str:
        return self._screen_canonical.get(name, name)

    def list_advanced_screens(self) -> Dict[str, str]:
        return dict(self._advanced_screens)

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

    def register_mascot_widget(self, widget: Optional[tk.Widget]) -> None:
        self._mascot_widget = widget

    def _get_mascot_widget(self) -> Optional[tk.Widget]:
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
        widget = self._get_mascot_widget()
        if widget and hasattr(widget, "react"):
            try:
                widget.react(kind)  # type: ignore[attr-defined]
            except Exception:
                pass

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

    def _register_optional_screen(
        self, key: str, module_name: str, class_name: str, *, label: Optional[str] = None
    ) -> None:
        try:
            module = import_module(module_name)
        except Exception as exc:
            self.logger.debug(
                "No se pudo importar el módulo opcional %s: %s", module_name, exc
            )
            return
        screen_cls = getattr(module, class_name, None)
        if screen_cls is None:
            self.logger.debug(
                "El módulo %s no define %s; omitiendo pantalla opcional", module_name, class_name
            )
            return
        aliases: tuple[str, ...] = ()
        class_name = getattr(screen_cls, "name", None)
        if class_name and class_name != key:
            aliases = (class_name,)
        self._register_screen(screen_cls, key=key, label=label, aliases=aliases, advanced=True)

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
        payload = {
            "barcode": code,
            "name": label,
            "source": "off" if stored else "scan",
        }
        self._append_food_event(payload)
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
        self._append_food_event({"name": label, "confidence": float(confidence), "source": "vision"})
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

    # ------------------------------------------------------------------ Nightscout / BG
    def on_bg_update(self, value: int, direction: str = "") -> None:
        self._last_bg = int(value)
        self._last_bg_direction = direction
        state = self.state.update_bg(value, direction)
        if self.diabetes_mode and value < 70:
            self._show_hypo_prompt(value)
        elif state.get("normalized") and self.hypo_timer.is_running():
            self.on_hypo_timer_finished()

    def on_bg_error(self, message: str) -> None:
        self.logger.warning("Nightscout: %s", message)
        self.mascot_react("error")
        text = (message or "Error Nightscout").strip()
        self.show_mascot_message(text, kind="error", priority=7, icon="⚠️", ttl_ms=3600)

    def _show_hypo_prompt(self, bg_value: int) -> None:
        if self.state.hypo_modal_open or self.hypo_timer.is_running():
            return
        self.state.hypo_modal_open = True
        self.mascot_react("error")
        self.show_mascot_message("hypo_alert", bg_value, kind="warning", priority=8, icon="🩸", ttl_ms=4200)
        try:
            self.hypo_overlay.present(bg_value)
        except Exception:
            self.state.hypo_modal_open = False

    def start_hypo_timer(self) -> None:
        if self.hypo_timer.is_running():
            self.show_mascot_message("hypo_timer_started", kind="info", priority=6, icon="⏱", ttl_ms=2400)
            return
        self.state.hypo_modal_open = False
        self._hypo_timer_started_ts = time.time()
        self.mascot_react("error")
        self.show_mascot_message("hypo_timer_started", kind="warning", priority=8, icon="⏱", ttl_ms=3600)
        if self.voice is not None:
            try:
                self.voice.speak("Hipoglucemia detectada, activa el temporizador")
            except Exception:
                self.logger.debug("No se pudo reproducir aviso de voz", exc_info=True)
        try:
            self.hypo_timer.open(duration=15 * 60)
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
        if self._hypo_timer_started_ts is None and not self.hypo_timer.is_running():
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
        try:
            weight = self.get_latest_weight()
        except Exception:
            weight = 0.0
        decimals = max(0, int(self.cfg.get("decimals", 0)))
        unit = str(self.cfg.get("unit", "g"))
        formatted = f"{weight:.{decimals}f} {unit}"
        stable = bool(self.reader.is_stable()) if self.reader else False

        self.weight_text.set(formatted)
        self.stability_text.set("Estable" if stable else "Midiendo…")
        try:
            self.topbar.update_weight(formatted, stable)
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
            "diabetes_mode": self.diabetes_mode,
            "hypo_timer_active": self.hypo_timer.is_running() if self.hypo_timer else False,
            "hypo_timer_remaining": self.hypo_timer.remaining_seconds() if self.hypo_timer else 0,
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


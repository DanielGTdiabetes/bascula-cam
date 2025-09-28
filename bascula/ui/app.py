"""Main Tk application controller for Bascula."""
from __future__ import annotations

import inspect
import logging
import os
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from ..config.pin import (
    CONFIG_YAML_PATH,
    PinPersistenceError,
    ensure_miniweb_pin,
    regenerate_miniweb_pin,
    reload_miniweb_config,
)
from ..config.settings import ScaleSettings, Settings
from ..runtime import HeartbeatWriter
from ..services.audio import AudioService
from ..system.audio_config import AudioCard, detect_primary_card, list_cards
from ..services.nightscout import NightscoutService
from ..services.nutrition import NutritionService
from ..services.scale import BackendUnavailable, ScaleService
from ..utils import load_config as load_legacy_config, save_config as save_legacy_config
from .screens import FoodsScreen, HomeScreen, RecipesScreen
from .screens_tabs_ext import TabbedSettingsMenuScreen
from .icon_loader import load_icon
from .theme_ctk import (
    COLORS as HOLO_COLORS,
    CTK_AVAILABLE,
    create_button as holo_button,
    create_frame as holo_frame,
    create_label as holo_label,
    create_root,
    font_tuple,
)
from .ui_config import dump_ui_config, load_ui_config
from . import theme_holo
from .views.timer import TimerController, TimerDialog, TimerEvent, TimerState
from .windowing import apply_kiosk_window_prefs

from PIL import Image

import yaml

if TYPE_CHECKING:
    from .views.home import HomeView

try:  # pragma: no cover - optional dependency when CTk is available
    from customtkinter import CTkImage  # type: ignore
except Exception:  # pragma: no cover - gracefully degrade without customtkinter
    CTkImage = None  # type: ignore

log = logging.getLogger(__name__)


class PassiveScaleService:
    """Fallback scale service that keeps the UI responsive without data."""

    name = "PASSIVE"

    def __init__(self, settings: ScaleSettings, *, logger: Optional[logging.Logger] = None) -> None:
        self.logger = logger or log
        self._callbacks: list[Callable[..., None]] = []
        self._unit = str((settings.unit or "g").lower()) if settings.unit else "g"
        self._unit = "ml" if self._unit == "ml" else "g"
        self._decimals = 1 if int(getattr(settings, "decimals", 0) or 0) > 0 else 0
        self._calibration_factor = float(getattr(settings, "calib_factor", 1.0) or 1.0)
        self._ml_factor = float(getattr(settings, "ml_factor", 1.0) or 1.0)
        if self._ml_factor <= 0:
            self._ml_factor = 1.0

    # ------------------------------------------------------------------
    def start(self) -> None:
        self._notify_all()

    def stop(self) -> None:  # pragma: no cover - interface compatibility
        return

    close = stop

    # ------------------------------------------------------------------
    def subscribe(self, callback: Callable[..., None]) -> None:
        if not callable(callback):
            return
        if callback not in self._callbacks:
            self._callbacks.append(callback)
        self._notify(callback)

    def unsubscribe(self, callback: Callable[..., None]) -> None:
        try:
            self._callbacks.remove(callback)
        except ValueError:
            pass

    def _notify_all(self) -> None:
        for callback in list(self._callbacks):
            self._notify(callback)

    def _notify(self, callback: Callable[..., None]) -> None:
        try:
            params = inspect.signature(callback).parameters
            if len(params) >= 3:
                callback(None, False, self._unit)
            else:
                callback(None, False)
        except Exception:  # pragma: no cover - defensive
            self.logger.debug("Passive scale callback failed", exc_info=True)

    # ------------------------------------------------------------------
    def tare(self) -> None:  # pragma: no cover - no hardware
        return

    def zero(self) -> None:  # pragma: no cover - no hardware
        return

    def toggle_units(self) -> str:
        self._unit = "ml" if self._unit == "g" else "g"
        self._notify_all()
        return self._unit

    def set_unit(self, unit: str) -> str:
        self._unit = "ml" if str(unit or "").lower() == "ml" else "g"
        self._notify_all()
        return self._unit

    def get_unit(self) -> str:
        return self._unit

    def set_calibration_factor(self, factor: float) -> float:
        try:
            value = float(factor)
        except (TypeError, ValueError):
            return self._calibration_factor
        if abs(value) < 1e-6:
            return self._calibration_factor
        self._calibration_factor = value
        return self._calibration_factor

    def get_calibration_factor(self) -> float:
        return self._calibration_factor

    def set_ml_factor(self, ml_factor: float) -> float:
        try:
            value = float(ml_factor)
        except (TypeError, ValueError):
            return self._ml_factor
        if value <= 0:
            return self._ml_factor
        self._ml_factor = value
        return self._ml_factor

    def get_ml_factor(self) -> float:
        return self._ml_factor

    def set_decimals(self, decimals: int) -> int:
        try:
            value = int(decimals)
        except (TypeError, ValueError):
            value = self._decimals
        self._decimals = 1 if value > 0 else 0
        self._notify_all()
        return self._decimals

    def get_decimals(self) -> int:
        return self._decimals

    def get_last_weight_g(self) -> float:
        return 0.0


class BasculaApp:
    """Application entry point responsible for wiring UI and services."""

    def __init__(self) -> None:
        self.root = create_root()
        apply_kiosk_window_prefs(self.root)
        self.root.title("Báscula Cam")
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)

        self.heartbeat = HeartbeatWriter()
        self.heartbeat.start()

        self.settings = Settings.load()
        self._config_yaml_path = CONFIG_YAML_PATH
        self._config_yaml: Dict[str, Any] = self._load_config_yaml()
        self._ui_cfg: Dict[str, Any] = load_ui_config()
        yaml_ui = self._config_yaml.get("ui") if isinstance(self._config_yaml.get("ui"), dict) else {}
        if not isinstance(yaml_ui, dict):
            yaml_ui = {}
        mascota_from_yaml = yaml_ui.get("show_mascota") if isinstance(yaml_ui, dict) else None
        initial_yaml_missing = mascota_from_yaml is None
        if mascota_from_yaml is None:
            mascota_enabled = bool(self._ui_cfg.get("show_mascota", False))
        else:
            mascota_enabled = bool(mascota_from_yaml)
        yaml_ui.setdefault("show_mascota", mascota_enabled)
        self._config_yaml["ui"] = yaml_ui
        ui_had_key = "show_mascota" in self._ui_cfg
        self._ui_cfg["show_mascota"] = mascota_enabled
        self._mascota_enabled = bool(mascota_enabled)
        self._modal_depth = 0
        self._home_view: "HomeView | None" = None
        if initial_yaml_missing:
            self._save_config_yaml()
        if not ui_had_key:
            self._save_ui_cfg()
        self._miniweb_owner = os.environ.get("BASCULA_MINIWEB_OWNER", "pi")
        self._miniweb_group = os.environ.get("BASCULA_MINIWEB_GROUP", "pi")
        self._miniweb_pin = str(self.settings.network.miniweb_pin or "").strip()
        try:
            ensured_pin, created = ensure_miniweb_pin(
                config_path=self._config_yaml_path,
                owner=self._miniweb_owner,
                group=self._miniweb_group,
            )
        except PinPersistenceError:
            log.exception("No se pudo inicializar el PIN de la mini-web")
            ensured_pin, created = self._miniweb_pin, False
        if ensured_pin:
            if ensured_pin != self._miniweb_pin:
                self._miniweb_pin = ensured_pin
                self.settings.network.miniweb_pin = ensured_pin
                try:
                    self.settings.save()
                except Exception:
                    log.debug(
                        "No se pudo guardar la configuración tras inicializar el PIN",
                        exc_info=True,
                    )
            if created:
                reload_miniweb_config()
        else:
            self._miniweb_pin = self._miniweb_pin or ""
        self._cfg: Dict[str, Any] = self._load_legacy_cfg()
        self._audio_cards: list[AudioCard] = []
        self._audio_device_map: dict[str, str] = {}
        self._audio_device_labels: list[str] = []
        self.current_audio_device = (self.settings.audio.audio_device or "default").strip() or "default"
        self._load_audio_devices(save_on_change=True)

        self.audio_service = AudioService(
            audio_device=self.current_audio_device,
            volume=self.settings.general.volume,
            voice_model=self.settings.audio.voice_model or None,
            tts_enabled=self.settings.general.tts_enabled,
        )
        self.audio_service.set_enabled(self.settings.general.sound_enabled)
        self.audio_service.set_tts_enabled(self.settings.general.tts_enabled)

        self.scale_service = self._init_scale_service()
        self.nutrition_service = NutritionService()
        self.nightscout_service = NightscoutService(self.settings.diabetes)

        self.scale_service.subscribe(self._on_weight)
        self.scale_service.start()
        self.nightscout_service.set_listener(self._on_glucose)
        self.nightscout_service.start()

        self._timer_controller = TimerController(self.root, on_finish=self._on_timer_finished)
        self._timer_last_event = TimerEvent(TimerState.IDLE, None)
        self._timer_controller.add_listener(self._on_timer_event)
        self._timer_dialog: TimerDialog | None = None
        self._timer_last_dialog_value = self._timer_controller.open_dialog_initial()
        self._nav_history: list[str] = []
        self._current_route: Optional[str] = None
        self._escape_binding: Optional[str] = None
        self._sound_icon_on: object | None = None
        self._sound_icon_off: object | None = None
        self._glucose_label_visible = False
        self._glucose_pack: Dict[str, object] | None = None
        self._glucose_default_color: str | None = None

        self._build_toolbar()
        self._build_state_vars()
        self._build_router()
        self._apply_debug_shortcuts()

        self._apply_cfg_to_runtime(self._cfg, initial=True)

        self.navigate("home")

    # ------------------------------------------------------------------
    def _init_scale_service(self):
        try:
            return ScaleService(self.settings.scale)
        except BackendUnavailable as exc:
            log.error("Scale backend unavailable: %s", exc)
            log.warning("Scale service running in passive mode (showing --)")
            return PassiveScaleService(self.settings.scale, logger=log)

    # ------------------------------------------------------------------
    def _load_audio_devices(self, *, save_on_change: bool) -> None:
        try:
            cards = list_cards()
        except Exception:
            log.debug("No se pudieron enumerar las tarjetas ALSA", exc_info=True)
            cards = []

        self._audio_cards = cards
        self._audio_device_map = {"Automático (default)": "default"}
        self._audio_device_labels = ["Automático (default)"]

        for card in cards:
            label = f"Tarjeta {card.index}: {card.pretty_name}"
            self._audio_device_map[label] = card.device_string
            self._audio_device_labels.append(label)

        configured = (self.settings.audio.audio_device or "default").strip() or "default"
        valid_devices = set(self._audio_device_map.values())
        if configured not in valid_devices:
            if cards:
                preferred = detect_primary_card(cards) or cards[0]
                configured = preferred.device_string
                log.info(
                    "Audio device updated to %s (%s)",
                    configured,
                    preferred.pretty_name,
                )
            else:
                configured = "default"
            self.settings.audio.audio_device = configured
            if save_on_change:
                try:
                    self.settings.save()
                except Exception:
                    log.debug("No se pudo guardar configuración tras ajustar audio", exc_info=True)

        self.current_audio_device = configured
        label = self._label_for_device(configured)
        if hasattr(self, "audio_device_choice_var"):
            try:
                self.audio_device_choice_var.set(label)
            except Exception:
                pass
        if cards:
            chosen = next((card for card in cards if card.device_string == configured), None)
            if chosen:
                log.info(
                    "Audio card in use: %s (%s)",
                    chosen.index,
                    chosen.pretty_name,
                )
        else:
            log.info("Audio device in use: %s", configured)

    def _label_for_device(self, device: str) -> str:
        for label, value in self._audio_device_map.items():
            if value == device:
                return label
        custom = f"Personalizado ({device})"
        self._audio_device_map[custom] = device
        if custom not in self._audio_device_labels:
            self._audio_device_labels.append(custom)
        return custom

    def get_audio_device_labels(self) -> list[str]:
        return list(self._audio_device_labels)

    def refresh_audio_devices(self) -> list[str]:
        self._load_audio_devices(save_on_change=False)
        if hasattr(self, "audio_device_status_var"):
            self.audio_device_status_var.set("Lista de tarjetas actualizada.")
        return self.get_audio_device_labels()

    # ------------------------------------------------------------------
    def _load_config_yaml(self) -> Dict[str, Any]:
        path = self._config_yaml_path
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle) or {}
            if isinstance(data, dict):
                return data
        except FileNotFoundError:
            return {}
        except Exception:
            log.debug("No se pudo leer %s", path, exc_info=True)
        return {}

    def _save_config_yaml(self) -> None:
        try:
            self._config_yaml_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        try:
            with self._config_yaml_path.open("w", encoding="utf-8") as handle:
                yaml.safe_dump(self._config_yaml, handle, sort_keys=False, allow_unicode=True)
        except Exception:
            log.debug("No se pudo guardar %s", self._config_yaml_path, exc_info=True)

    # ------------------------------------------------------------------
    def _load_legacy_cfg(self) -> Dict[str, Any]:
        try:
            cfg = load_legacy_config()
            if not isinstance(cfg, dict):
                cfg = {}
        except Exception:
            log.debug("No se pudo cargar configuración heredada", exc_info=True)
            cfg = {}

        cfg["sound_enabled"] = bool(self.settings.general.sound_enabled)
        cfg["decimals"] = int(getattr(self.settings.scale, "decimals", 0))
        cfg["unit"] = str(getattr(self.settings.scale, "unit", "g") or "g")
        cfg["calib_factor"] = float(getattr(self.settings.scale, "calibration_factor", 1.0))
        cfg["ml_factor"] = float(getattr(self.settings.scale, "ml_factor", 1.0))
        cfg["port"] = str(getattr(self.settings.scale, "port", ""))
        cfg["smoothing"] = int(getattr(self.settings.scale, "smoothing", 5))
        return cfg

    def _apply_cfg_to_runtime(self, cfg: Dict[str, Any], *, initial: bool = False) -> None:
        if not isinstance(cfg, dict):
            return

        sound_enabled = bool(cfg.get("sound_enabled", True))
        if hasattr(self, "general_sound_var"):
            try:
                self.general_sound_var.set(sound_enabled)
            except Exception:
                pass
        else:
            self.audio_service.set_enabled(sound_enabled)
        cfg["sound_enabled"] = sound_enabled
        self._apply_sound_icon(sound_enabled)

        decimals_raw = cfg.get("decimals", 0)
        try:
            decimals_value = 1 if int(decimals_raw) > 0 else 0
        except Exception:
            decimals_value = 0
        try:
            applied_decimals = self.scale_service.set_decimals(decimals_value)
        except Exception:
            applied_decimals = decimals_value
        cfg["decimals"] = int(applied_decimals)
        if hasattr(self, "scale_decimals_var"):
            try:
                self.scale_decimals_var.set(int(applied_decimals))
            except Exception:
                pass
        home_screen = None
        if isinstance(getattr(self, "screens", None), dict):
            home_screen = self.screens.get("home")
        if home_screen is not None:
            try:
                home_screen.view.set_decimals(int(applied_decimals))
            except Exception:
                pass

        desired_unit = str(cfg.get("unit", "g") or "g").lower()
        if desired_unit not in {"g", "ml"}:
            desired_unit = "g"
        try:
            current_unit = self.scale_service.get_unit()
        except Exception:
            current_unit = None
        if current_unit != desired_unit:
            try:
                desired_unit = self.scale_service.set_unit(desired_unit)
            except Exception:
                pass
        cfg["unit"] = desired_unit
        if hasattr(self, "scale_unit_var"):
            try:
                self.scale_unit_var.set(desired_unit)
            except Exception:
                pass
        if home_screen is not None:
            try:
                home_screen.view.set_units(desired_unit)
            except Exception:
                pass

        if not initial:
            self._persist_settings()

    # ------------------------------------------------------------------
    def get_cfg(self) -> Dict[str, Any]:
        return self._cfg

    def get_ui_cfg(self) -> Dict[str, Any]:
        return dict(self._ui_cfg)

    def save_cfg(self) -> None:
        try:
            save_legacy_config(self._cfg)
        except Exception:
            log.debug("No se pudo guardar configuración heredada", exc_info=True)
        try:
            self._apply_cfg_to_runtime(self._cfg)
        except Exception:
            log.debug("No se pudo aplicar configuración heredada", exc_info=True)

    def _save_ui_cfg(self) -> None:
        try:
            dump_ui_config(self._ui_cfg)
        except Exception:
            log.debug("No se pudo guardar configuración de la UI", exc_info=True)

    def register_home_view(self, view: "HomeView") -> None:
        self._home_view = view
        self._update_mascota_visibility()

    def set_mascota_enabled(self, enabled: bool) -> None:
        self._mascota_enabled = bool(enabled)
        self._ui_cfg["show_mascota"] = self._mascota_enabled
        self._save_ui_cfg()
        ui_section = self._config_yaml.get("ui") if isinstance(self._config_yaml.get("ui"), dict) else {}
        if not isinstance(ui_section, dict):
            ui_section = {}
        ui_section["show_mascota"] = self._mascota_enabled
        self._config_yaml["ui"] = ui_section
        self._save_config_yaml()
        log.info("Mascota %s", "activada" if self._mascota_enabled else "desactivada")
        self._update_mascota_visibility()

    def notify_modal_opened(self) -> None:
        self._modal_depth += 1
        self._update_mascota_visibility()

    def notify_modal_closed(self) -> None:
        if self._modal_depth > 0:
            self._modal_depth -= 1
        else:
            self._modal_depth = 0
        self._update_mascota_visibility()

    def _update_mascota_visibility(self) -> None:
        view = self._home_view
        if view is None:
            return
        should_show = self._mascota_enabled and self._modal_depth == 0 and self._current_route == "home"
        try:
            if should_show:
                view.show_mascota()
            else:
                view.hide_mascota()
        except Exception:
            log.debug("No se pudo actualizar la visibilidad de la mascota", exc_info=True)

    def get_audio(self) -> AudioService:
        return self.audio_service

    # ------------------------------------------------------------------
    def _build_toolbar(self) -> None:
        title_font = font_tuple(14, "bold") if CTK_AVAILABLE else ("DejaVu Sans", 14, "bold")

        if CTK_AVAILABLE:
            self.toolbar = holo_frame(self.root, fg_color=HOLO_COLORS["surface"])
        else:
            self.toolbar = tk.Frame(self.root, bg="white", bd=0, relief="flat")
        self.toolbar.pack(fill="x")

        self.glucose_var = tk.StringVar(value="")
        if CTK_AVAILABLE:
            self.glucose_label = holo_label(
                self.toolbar,
                textvariable=self.glucose_var,
                font=title_font,
                text_color=HOLO_COLORS["primary"],
            )
            self._glucose_default_color = HOLO_COLORS["primary"]
            self._glucose_pack = {"side": "left", "padx": 16, "pady": 12}
        else:
            self.glucose_label = tk.Label(
                self.toolbar,
                textvariable=self.glucose_var,
                font=title_font,
                fg="#0050d0",
                bg="white",
            )
            self._glucose_default_color = "#0050d0"
            self._glucose_pack = {"side": "left", "padx": 16, "pady": 12}

        self.timer_var = tk.StringVar(value="")
        if CTK_AVAILABLE:
            timer_color = HOLO_COLORS["text"]
            self.timer_label = holo_label(
                self.toolbar,
                textvariable=self.timer_var,
                font=title_font,
                text_color=timer_color,
            )
            self.timer_label.pack(side="left", padx=16)
            self._timer_color_default = timer_color
        else:
            timer_color = "#1f2430"
            self.timer_label = tk.Label(
                self.toolbar,
                textvariable=self.timer_var,
                font=title_font,
                fg=timer_color,
                bg="white",
            )
            self.timer_label.pack(side="left", padx=16)
            self._timer_color_default = timer_color

        try:
            self.timer_label.configure(cursor="hand2")
        except Exception:
            pass
        self.timer_label.bind("<Button-1>", self._on_timer_label_left, add=True)
        self.timer_label.bind("<Button-3>", self._on_timer_label_right, add=True)

        if CTK_AVAILABLE:
            button_font = font_tuple(18, "bold")
            self.sound_button = holo_button(
                self.toolbar,
                text="",
                command=self.toggle_sound,
                width=44,
                font=button_font,
                fg_color=HOLO_COLORS["surface_alt"],
                hover_color=HOLO_COLORS["accent"],
            )
            self.sound_button.pack(side="left", padx=10)
            self._load_sound_icons(36)
            self._apply_sound_icon(self.settings.general.sound_enabled)
        else:
            self.sound_button = tk.Button(
                self.toolbar,
                text="",
                command=self.toggle_sound,
                bg="white",
                fg="#1f2430",
                bd=0,
                relief="flat",
                font=("DejaVu Sans", 16),
                takefocus=0,
            )
            try:
                self.sound_button.configure(highlightthickness=0)
            except Exception:
                pass
            self.sound_button.pack(side="left", padx=10)
            self._load_sound_icons(28)
            self._apply_sound_icon(self.settings.general.sound_enabled)

        self._refresh_glucose_indicator()

    def _build_state_vars(self) -> None:
        self.general_sound_var = tk.BooleanVar(value=self.settings.general.sound_enabled)
        self.general_volume_var = tk.IntVar(value=self.settings.general.volume)
        self.general_tts_var = tk.BooleanVar(value=self.settings.general.tts_enabled)
        self.voice_model_var = tk.StringVar(value=self.settings.audio.voice_model or "")
        self.audio_device_choice_var = tk.StringVar(
            value=self._label_for_device(self.current_audio_device)
        )
        self.audio_device_status_var = tk.StringVar(
            value=f"Salida de audio: {self.audio_device_choice_var.get()}"
        )
        self.general_sound_var.trace_add("write", lambda *_: self._sync_sound())
        self.general_volume_var.trace_add(
            "write", lambda *_: self.audio_service.set_volume(self.general_volume_var.get())
        )
        self.general_tts_var.trace_add(
            "write", lambda *_: self.audio_service.set_tts_enabled(self.general_tts_var.get())
        )
        self.audio_device_choice_var.trace_add(
            "write", lambda *_: self._on_audio_device_label_change()
        )

        self.scale_calibration_var = tk.StringVar(
            value=self._format_float(self.settings.scale.calibration_factor)
        )
        self.scale_density_var = tk.StringVar(value=self._format_float(self.settings.scale.ml_factor))
        self.scale_decimals_var = tk.IntVar(value=int(self.settings.scale.decimals))
        self.scale_unit_var = tk.StringVar(value=self.scale_service.get_unit())

        self.diabetes_enabled_var = tk.BooleanVar(value=self.settings.diabetes.diabetes_enabled)
        self.diabetes_url_var = tk.StringVar(value=self.settings.diabetes.ns_url)
        self.diabetes_token_var = tk.StringVar(value=self.settings.diabetes.ns_token)
        self.diabetes_hypo_var = tk.IntVar(value=int(self.settings.diabetes.hypo_alarm))
        self.diabetes_hyper_var = tk.IntVar(value=int(self.settings.diabetes.hyper_alarm))
        self.diabetes_mode1515_var = tk.BooleanVar(value=self.settings.diabetes.mode_15_15)
        self.diabetes_ratio_var = tk.DoubleVar(value=float(self.settings.diabetes.insulin_ratio))
        self.diabetes_sensitivity_var = tk.DoubleVar(
            value=float(self.settings.diabetes.insulin_sensitivity)
        )
        self.diabetes_target_var = tk.IntVar(value=int(self.settings.diabetes.target_glucose))

        self.miniweb_enabled_var = tk.BooleanVar(value=self.settings.network.miniweb_enabled)
        self.miniweb_port_var = tk.IntVar(value=int(self.settings.network.miniweb_port))
        self.miniweb_pin_var = tk.StringVar(value=self._miniweb_pin)

    def _build_router(self) -> None:
        if CTK_AVAILABLE:
            self.container = holo_frame(self.root, fg_color=HOLO_COLORS["bg"])
        else:
            self.container = tk.Frame(self.root, bg="white")
        self.container.pack(fill="both", expand=True)

        self.screens = {
            "home": HomeScreen(self.container, self),
            "alimentos": FoodsScreen(self.container, self),
            "recetas": RecipesScreen(self.container, self),
            "settings": TabbedSettingsMenuScreen(self.container, self),
        }
        for screen in self.screens.values():
            screen.place(relx=0, rely=0, relwidth=1, relheight=1)

    def _apply_debug_shortcuts(self) -> None:
        if os.getenv("BASCULA_DEBUG_KIOSK") == "1":
            self.root.bind("<F8>", lambda _e: self.navigate("home"))
            self.root.bind("<F9>", lambda _e: self.navigate("home"))
            self.root.bind("<F10>", lambda _e: self.navigate("settings"))

    # ------------------------------------------------------------------
    def navigate(self, route: str, *, push: bool = True) -> None:
        screen = self.screens.get(route)
        if not screen:
            log.warning("Pantalla desconocida: %s", route)
            return
        previous = self._current_route
        self._current_route = route
        if push:
            if not self._nav_history or self._nav_history[-1] != route:
                self._nav_history.append(route)
        else:
            if self._nav_history:
                self._nav_history[-1] = route
            else:
                self._nav_history.append(route)
        screen.lift()
        log.info("Pantalla activa: %s", route)
        if route == "settings" and previous != "settings":
            log.info("UI: open Settings")
        if previous == "settings" and route != "settings":
            log.info("UI: back from Settings")
        self._update_escape_binding()
        self._update_mascota_visibility()

    def show_screen(self, route: str) -> None:  # backwards compatibility
        self.navigate(route)

    def go_back(self) -> None:
        if len(self._nav_history) <= 1:
            self.go_home()
            return
        self._nav_history.pop()
        target = self._nav_history[-1]
        self.navigate(target, push=False)

    def go_home(self) -> None:
        self._nav_history = ["home"]
        self.navigate("home", push=False)

    def _update_escape_binding(self) -> None:
        if self._escape_binding is not None:
            try:
                self.root.unbind("<Escape>", self._escape_binding)
            except Exception:
                pass
            self._escape_binding = None
        if self._current_route == "settings":
            self._escape_binding = self.root.bind("<Escape>", lambda _e: self.go_back())

    # ------------------------------------------------------------------
    def _on_weight(self, value: Optional[float], stable: bool, unit: str) -> None:
        self.root.after(0, lambda: self.screens["home"].update_weight(value, stable, unit))

    def _on_glucose(self, reading) -> None:
        def _update() -> None:
            text = f"Glucosa {reading.glucose_mgdl} {reading.direction}".strip()
            self._refresh_glucose_indicator(text=text)

        self.root.after(0, _update)

    # ------------------------------------------------------------------
    def toggle_sound(self) -> None:
        enabled = not self.general_sound_var.get()
        self.general_sound_var.set(enabled)
        self._sync_sound()
        self.save_cfg()

    def _sync_sound(self) -> None:
        enabled = self.general_sound_var.get()
        self.audio_service.set_enabled(enabled)
        self._apply_sound_icon(enabled)
        self._cfg["sound_enabled"] = bool(enabled)

    def _load_sound_icons(self, size: int) -> None:
        icon_dir = Path(__file__).parent / "assets" / "icons"
        on_path = icon_dir / "speaker.png"
        off_path = icon_dir / "speaker_muted.png"
        self._sound_icon_on = None
        self._sound_icon_off = None

        if CTK_AVAILABLE and CTkImage is not None:
            try:
                with Image.open(on_path) as image_on:
                    on_image = image_on.copy()
                with Image.open(off_path) as image_off:
                    off_image = image_off.copy()
                self._sound_icon_on = CTkImage(  # type: ignore[operator]
                    light_image=on_image, dark_image=on_image, size=(size, size)
                )
                self._sound_icon_off = CTkImage(  # type: ignore[operator]
                    light_image=off_image, dark_image=off_image, size=(size, size)
                )
            except Exception:
                self._sound_icon_on = None
                self._sound_icon_off = None
            return

        try:
            self._sound_icon_on = load_icon("speaker.png", size)
        except Exception:
            self._sound_icon_on = None
        try:
            self._sound_icon_off = load_icon("speaker_muted.png", size)
        except Exception:
            self._sound_icon_off = None

    def _apply_sound_icon(self, enabled: bool) -> None:
        button = getattr(self, "sound_button", None)
        if button is None:
            return

        icon = self._sound_icon_on if enabled else self._sound_icon_off
        if icon is not None:
            try:
                button.configure(image=icon, text="")
                if not (CTK_AVAILABLE and CTkImage is not None):
                    button.image = icon  # type: ignore[attr-defined]
                return
            except Exception:
                pass

        try:
            button.configure(text="🔊" if enabled else "🔇")
        except Exception:
            pass

    def _should_display_glucose(self) -> bool:
        diabetes = getattr(self.settings, "diabetes", None)
        if diabetes is None:
            return False
        enabled = bool(getattr(diabetes, "diabetes_enabled", False))
        url = str(getattr(diabetes, "ns_url", "") or "").strip()
        return enabled and bool(url)

    def _refresh_glucose_indicator(self, text: Optional[str] = None, color: Optional[str] = None) -> None:
        label = getattr(self, "glucose_label", None)
        if label is None:
            return

        if text is not None:
            self.glucose_var.set(text)

        if not self._should_display_glucose():
            self.glucose_var.set("")
            if self._glucose_label_visible:
                try:
                    label.pack_forget()
                except Exception:
                    pass
                self._glucose_label_visible = False
            return

        current = (self.glucose_var.get() or "").strip()
        if not current:
            if self._glucose_label_visible:
                try:
                    label.pack_forget()
                except Exception:
                    pass
                self._glucose_label_visible = False
            return

        if not self._glucose_label_visible:
            pack_opts = self._glucose_pack or {"side": "left", "padx": 16, "pady": 12}
            try:
                label.pack(**pack_opts)
            except Exception:
                return
            self._glucose_label_visible = True

        target_color = color or self._glucose_default_color
        if target_color:
            try:
                if CTK_AVAILABLE:
                    label.configure(text_color=target_color)
                else:
                    label.configure(fg=target_color)
            except Exception:
                pass


    def _on_audio_device_label_change(self) -> None:
        label = self.audio_device_choice_var.get()
        device = self._audio_device_map.get(label)
        if not device or device == self.settings.audio.audio_device:
            return
        self.settings.audio.audio_device = device
        self.current_audio_device = device
        self.audio_service.set_device(device)
        self.audio_device_status_var.set(f"Salida de audio: {label}")
        log.info("UI: audio device changed to %s (%s)", device, label)
        if self.general_sound_var.get():
            try:
                self.audio_service.beep_ok()
            except Exception:
                log.debug("No se pudo reproducir beep tras cambiar de tarjeta", exc_info=True)

    def _format_float(self, value: float) -> str:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = 0.0
        return f"{numeric:.6g}"

    def apply_scale_settings(self) -> None:
        errors: list[str] = []
        try:
            calib_value = float(self.scale_calibration_var.get())
        except (TypeError, ValueError):
            errors.append("calibración")
            calib_value = self.scale_service.get_calibration_factor()
        else:
            applied = self.scale_service.set_calibration_factor(calib_value)
            self.scale_calibration_var.set(self._format_float(applied))
            self._cfg["calib_factor"] = float(applied)

        try:
            density_value = float(self.scale_density_var.get())
        except (TypeError, ValueError):
            errors.append("densidad ml")
            density_value = self.scale_service.get_ml_factor()
        else:
            applied_ml = self.scale_service.set_ml_factor(density_value)
            self.scale_density_var.set(self._format_float(applied_ml))
            self._cfg["ml_factor"] = float(applied_ml)

        try:
            decimals_value = int(self.scale_decimals_var.get())
        except (TypeError, ValueError):
            errors.append("decimales")
            decimals_value = self.scale_service.get_decimals()
        decimals_applied = self.scale_service.set_decimals(decimals_value)
        self.scale_decimals_var.set(decimals_applied)
        self._cfg["decimals"] = int(decimals_applied)

        unit_applied = self.scale_service.set_unit(self.scale_unit_var.get())
        self.scale_unit_var.set(unit_applied)
        self._cfg["unit"] = unit_applied

        if errors:
            messagebox.showerror(
                "Valores inválidos",
                "No se pudo actualizar: " + ", ".join(errors),
            )
        else:
            self.audio_service.beep_ok()
            self.save_cfg()

    # ------------------------------------------------------------------
    def handle_tare(self) -> None:
        self.scale_service.tare()
        self.audio_service.beep_ok()

    def handle_zero(self) -> None:
        self.scale_service.zero()
        self.audio_service.beep_ok()

    def handle_toggle_units(self) -> str:
        mode = self.scale_service.toggle_units()
        self._cfg["unit"] = mode
        self.save_cfg()
        return mode

    def handle_timer(self) -> None:
        self.open_timer_dialog()

    def open_timer_dialog(self, initial_seconds: int | None = None) -> None:
        dialog = self._ensure_timer_dialog()
        if dialog is None:
            return

        if initial_seconds is None:
            if (
                self._timer_last_event.state in {TimerState.RUNNING, TimerState.PAUSED}
                and self._timer_last_event.remaining
            ):
                base_value = int(self._timer_last_event.remaining)
            else:
                base_value = int(self._timer_last_dialog_value)
        else:
            base_value = int(initial_seconds)

        dialog.set_last_programmed(self._timer_last_dialog_value)
        dialog.update_from_event(self._timer_last_event)
        self.notify_modal_opened()
        dialog.show(initial_seconds=base_value)

    def timer_start(self, total_seconds: int) -> None:
        seconds = max(1, int(total_seconds))
        self._timer_last_dialog_value = seconds
        self._timer_controller.start(seconds)

    def timer_pause(self) -> None:
        self._timer_controller.pause()

    def timer_resume(self) -> None:
        self._timer_controller.resume()

    def timer_cancel(self) -> None:
        self._timer_controller.cancel()

    def timer_get_remaining(self) -> int:
        return self._timer_controller.get_remaining()

    # ------------------------------------------------------------------
    def _ensure_timer_dialog(self) -> TimerDialog | None:
        dialog = self._timer_dialog
        if dialog is not None:
            try:
                if int(dialog.winfo_exists()):
                    return dialog
            except Exception:
                self._timer_dialog = None

        dialog = TimerDialog(self.root, controller=self)
        dialog.bind("<Destroy>", self._on_timer_dialog_destroyed, add=True)
        dialog.bind("<Unmap>", self._on_timer_dialog_hidden, add=True)
        self._timer_dialog = dialog
        return dialog

    def _on_timer_dialog_hidden(self, _event: tk.Event | None = None) -> None:
        self.notify_modal_closed()

    def _on_timer_dialog_destroyed(self, _event: tk.Event | None = None) -> None:
        self._timer_dialog = None

    def _on_timer_event(self, event: TimerEvent) -> None:
        self._timer_last_event = event
        self._update_timer_indicator(event)

        dialog = self._timer_dialog
        if dialog is None:
            return
        try:
            if int(dialog.winfo_exists()):
                dialog.update_from_event(event)
        except Exception:
            self._timer_dialog = None

    def _update_timer_indicator(self, event: TimerEvent) -> None:
        state = event.state
        if state in {TimerState.IDLE, TimerState.CANCELLED}:
            self.timer_var.set("")
            self._set_timer_label_color(self._timer_color_default)
            return

        remaining = int(event.remaining or 0)
        display_seconds = remaining if state != TimerState.FINISHED else 0
        self.timer_var.set(f"⏱ {theme_holo.format_mmss(display_seconds)}")

        if state == TimerState.PAUSED:
            color = theme_holo.COLOR_TEXT_MUTED
        elif state == TimerState.FINISHED:
            if event.flash:
                color = theme_holo.PALETTE.get("danger", theme_holo.COLOR_ACCENT)
            else:
                color = self._timer_color_default
        else:
            color = theme_holo.PALETTE.get("primary", self._timer_color_default)

        self._set_timer_label_color(color)

    def _set_timer_label_color(self, color: Optional[str]) -> None:
        target_color = color or self._timer_color_default
        try:
            if CTK_AVAILABLE:
                self.timer_label.configure(text_color=target_color)
            else:
                self.timer_label.configure(fg=target_color)
        except Exception:
            pass

    def _on_timer_finished(self) -> None:
        try:
            self.audio_service.beep_alarm()
        except Exception:
            log.debug("No se pudo reproducir beep de temporizador", exc_info=True)
        try:
            self.audio_service.speak("El temporizador ha finalizado")
        except Exception:
            log.debug("No se pudo reproducir TTS de temporizador", exc_info=True)

    def _on_timer_label_left(self, _event: tk.Event) -> str | None:
        state = self._timer_last_event.state
        if state == TimerState.RUNNING:
            self.timer_pause()
        elif state == TimerState.PAUSED:
            self.timer_resume()
        elif state == TimerState.FINISHED:
            self.open_timer_dialog(initial_seconds=self._timer_last_dialog_value)
        else:
            self.open_timer_dialog()
        return "break"

    def _on_timer_label_right(self, _event: tk.Event) -> str | None:
        if self._timer_last_event.state in {TimerState.RUNNING, TimerState.PAUSED, TimerState.FINISHED}:
            self.timer_cancel()
        return "break"

    # ------------------------------------------------------------------
    def shutdown(self) -> None:
        try:
            self.save_cfg()
        except Exception:
            log.debug("No se pudo guardar configuración al cerrar", exc_info=True)
            self._persist_settings()
        self.scale_service.stop()
        self.nightscout_service.stop()
        if hasattr(self, "heartbeat"):
            try:
                self.heartbeat.stop()
            except Exception:
                log.debug("Error deteniendo heartbeat", exc_info=True)
        self.root.destroy()

    def _persist_settings(self) -> None:
        self.settings.general.sound_enabled = self.general_sound_var.get()
        self.settings.general.volume = self.general_volume_var.get()
        self.settings.general.tts_enabled = self.general_tts_var.get()
        self.settings.audio.audio_device = self.current_audio_device
        self.settings.audio.voice_model = self.voice_model_var.get()
        self.settings.scale.calibration_factor = self._safe_float(
            self.scale_calibration_var.get(),
            self.scale_service.get_calibration_factor(),
        )
        self.settings.scale.ml_factor = self._safe_float(
            self.scale_density_var.get(),
            self.scale_service.get_ml_factor(),
        )
        self.settings.scale.decimals = self._safe_int(
            self.scale_decimals_var.get(), self.settings.scale.decimals
        )
        self.settings.scale.unit_mode = self.scale_unit_var.get()
        self.settings.diabetes.diabetes_enabled = self.diabetes_enabled_var.get()
        self.settings.diabetes.ns_url = self.diabetes_url_var.get()
        self.settings.diabetes.ns_token = self.diabetes_token_var.get()
        self.settings.diabetes.hypo_alarm = self._safe_int(
            self.diabetes_hypo_var.get(), self.settings.diabetes.hypo_alarm
        )
        self.settings.diabetes.hyper_alarm = self._safe_int(
            self.diabetes_hyper_var.get(), self.settings.diabetes.hyper_alarm
        )
        self.settings.diabetes.mode_15_15 = self.diabetes_mode1515_var.get()
        self.settings.diabetes.insulin_ratio = self._safe_float(
            self.diabetes_ratio_var.get(), self.settings.diabetes.insulin_ratio
        )
        self.settings.diabetes.insulin_sensitivity = self._safe_float(
            self.diabetes_sensitivity_var.get(),
            self.settings.diabetes.insulin_sensitivity,
        )
        self.settings.diabetes.target_glucose = self._safe_int(
            self.diabetes_target_var.get(), self.settings.diabetes.target_glucose
        )
        self.settings.network.miniweb_enabled = self.miniweb_enabled_var.get()
        self.settings.network.miniweb_port = self._safe_int(
            self.miniweb_port_var.get(), self.settings.network.miniweb_port
        )
        self.settings.network.miniweb_pin = self._miniweb_pin
        self.settings.save()
        self._refresh_glucose_indicator()

    # ------------------------------------------------------------------
    def _update_miniweb_pin(self, value: str) -> None:
        self._miniweb_pin = str(value or "").strip()
        self.settings.network.miniweb_pin = self._miniweb_pin
        var = getattr(self, "miniweb_pin_var", None)
        if var is not None:
            try:
                var.set(self._miniweb_pin)
            except Exception:
                pass

    def get_miniweb_pin(self) -> str:
        return self._miniweb_pin

    def regenerate_miniweb_pin(self) -> str:
        try:
            new_pin = regenerate_miniweb_pin(
                config_path=self._config_yaml_path,
                owner=self._miniweb_owner,
                group=self._miniweb_group,
            )
        except (ValueError, PinPersistenceError) as exc:
            raise PinPersistenceError(str(exc)) from exc
        self._update_miniweb_pin(new_pin)
        reload_miniweb_config()
        try:
            self.settings.save()
        except Exception:
            log.debug(
                "No se pudo guardar la configuración tras regenerar el PIN",
                exc_info=True,
            )
        return new_pin

    @staticmethod
    def _safe_float(value, fallback: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(fallback)

    @staticmethod
    def _safe_int(value, fallback: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(fallback)

    def _restart_miniweb_service(self) -> None:
        try:
            proc = subprocess.run(
                ["systemctl", "restart", "bascula-miniweb.service"],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except FileNotFoundError:
            log.debug("systemctl no disponible para reiniciar la mini-web")
            return
        except Exception:
            log.debug("Error lanzando systemctl restart bascula-miniweb", exc_info=True)
            return

        if proc.returncode != 0:
            stderr = proc.stderr.strip()
            stdout = proc.stdout.strip()
            message = stderr or stdout or "Fallo al reiniciar bascula-miniweb"
            log.warning("No se pudo reiniciar bascula-miniweb: %s", message)

    # ------------------------------------------------------------------
    def discover_voice_models(self) -> list[tuple[str, str]]:
        candidates: list[Path] = []
        env_dirs = os.environ.get("BASCULA_PIPER_MODELS", "")
        for chunk in env_dirs.split(":"):
            chunk = chunk.strip()
            if chunk:
                candidates.append(Path(chunk))
        candidates.extend([Path("/opt/piper/models"), Path("/usr/share/piper/voices")])

        seen: set[str] = set()
        voices: list[tuple[str, str]] = []
        for base in candidates:
            if not base or not base.exists():
                continue
            for file in base.glob("*.onnx"):
                try:
                    resolved = str(file.resolve())
                except Exception:
                    resolved = str(file)
                if resolved in seen:
                    continue
                seen.add(resolved)
                folder = file.parent.name or "voz"
                label = f"{file.stem} ({folder})"
                voices.append((label, resolved))
        voices.sort(key=lambda item: item[0].lower())
        return voices

    def select_voice_model(self, model_path: str | None) -> bool:
        if not self.audio_service.set_voice_model(model_path or None):
            return False
        self.voice_model_var.set(model_path or "")
        self.settings.audio.voice_model = model_path or ""
        self._persist_settings()
        if self.general_tts_var.get():
            try:
                self.audio_service.speak("Voz actualizada")
            except Exception:
                log.debug("No se pudo reproducir voz de prueba", exc_info=True)
        else:
            self.audio_service.beep_ok()
        return True

    def apply_network_settings(self) -> None:
        self.settings.network.miniweb_enabled = self.miniweb_enabled_var.get()
        self.settings.network.miniweb_port = self._safe_int(
            self.miniweb_port_var.get(), self.settings.network.miniweb_port
        )
        self.settings.network.miniweb_pin = self._miniweb_pin
        self._persist_settings()
        self.miniweb_pin_var.set(self._miniweb_pin)
        self._restart_miniweb_service()
        self.audio_service.beep_ok()

    def apply_diabetes_settings(self) -> None:
        self.settings.diabetes.diabetes_enabled = self.diabetes_enabled_var.get()
        self.settings.diabetes.ns_url = self.diabetes_url_var.get()
        self.settings.diabetes.ns_token = self.diabetes_token_var.get()
        self.settings.diabetes.hypo_alarm = self._safe_int(
            self.diabetes_hypo_var.get(), self.settings.diabetes.hypo_alarm
        )
        self.settings.diabetes.hyper_alarm = self._safe_int(
            self.diabetes_hyper_var.get(), self.settings.diabetes.hyper_alarm
        )
        self.settings.diabetes.mode_15_15 = self.diabetes_mode1515_var.get()
        self.settings.diabetes.insulin_ratio = self._safe_float(
            self.diabetes_ratio_var.get(), self.settings.diabetes.insulin_ratio
        )
        self.settings.diabetes.insulin_sensitivity = self._safe_float(
            self.diabetes_sensitivity_var.get(),
            self.settings.diabetes.insulin_sensitivity,
        )
        self.settings.diabetes.target_glucose = self._safe_int(
            self.diabetes_target_var.get(), self.settings.diabetes.target_glucose
        )
        self._persist_settings()
        try:
            self.nightscout_service.stop()
            self.nightscout_service.settings = self.settings.diabetes
            self.nightscout_service.start()
        except Exception:
            log.debug("No se pudo reiniciar Nightscout tras guardar ajustes", exc_info=True)
        self._refresh_glucose_indicator()
        self.audio_service.beep_ok()

    # ------------------------------------------------------------------
    def run(self) -> None:
        self.root.mainloop()

    def __del__(self) -> None:  # pragma: no cover - best effort cleanup
        heartbeat = getattr(self, "heartbeat", None)
        if heartbeat is not None:
            try:
                heartbeat.stop()
            except Exception:
                pass
__all__ = ["BasculaApp"]

"""Tk application controller wiring services and views."""
from __future__ import annotations

import logging
import os
import queue
import threading
import time
import types
from pathlib import Path
from typing import Callable, Dict, Optional

import tkinter as tk

from .app_shell import AppShell
from .icon_loader import load_icon
from .windowing import apply_kiosk_window_prefs
from .views.home import HomeView
from .views.food_scanner import FoodScannerView
from .overlays.calibration import CalibrationOverlay
from .overlay_1515 import Protocol1515Overlay
from .overlays.timer import TimerController, TimerOverlay
from .theme_neo import COLORS, FONTS, SPACING
from .ui_config import CONFIG_PATH as UI_CONFIG_PATH, dump_ui_config, load_ui_config
from ..services.scale import ScaleService
from ..utils import load_config as load_main_config, save_config as save_main_config

try:  # pragma: no cover - optional dependency
    from ..services.camera import CameraService
except Exception:  # pragma: no cover - camera optional
    CameraService = None  # type: ignore

try:  # pragma: no cover - optional dependency
    from ..services.tts import PiperTTS
except Exception:  # pragma: no cover - bundled fallback below
    PiperTTS = None  # type: ignore

try:  # pragma: no cover - optional integration
    from ..services.nightscout import NightscoutClient
except Exception:  # pragma: no cover - optional integration
    NightscoutClient = None  # type: ignore

CFG_DIR = Path(os.environ.get("BASCULA_CFG_DIR", Path.home() / ".config/bascula"))
ICON_DIR = Path(__file__).resolve().parents[2] / "assets" / "icons"
LOG_PATH = Path("/var/log/bascula/app.log")
_LOGGING_CONFIGURED = False


def _configure_logging() -> None:
    """Ensure the UI logs to ``/var/log/bascula/app.log``."""

    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root_logger = logging.getLogger()

    file_handler: Optional[logging.Handler] = None
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
        file_handler.setFormatter(formatter)
    except Exception:
        file_handler = None

    if file_handler is not None:
        if not any(
            isinstance(handler, logging.FileHandler)
            and getattr(handler, "baseFilename", None) == str(LOG_PATH)
            for handler in root_logger.handlers
        ):
            root_logger.addHandler(file_handler)

    if not root_logger.handlers:
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)

    root_logger.setLevel(logging.INFO)

    _LOGGING_CONFIGURED = True


def _truthy(value: Optional[str]) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


class _LightScale:
    def __init__(self, decimals: int = 0, density: float = 1.0) -> None:
        self.decimals = int(decimals)
        self.density = float(density)
        self.net_weight = 0.0
        self.stable = True
        self.simulated = True

    def tare(self) -> None:  # pragma: no cover - trivial stub
        return None

    def zero(self) -> None:  # pragma: no cover - trivial stub
        return None

    def set_density(self, density: float) -> float:
        self.density = float(density)
        return self.density

    def set_decimals(self, decimals: int) -> int:
        self.decimals = int(decimals)
        return self.decimals

    def stop(self) -> None:  # pragma: no cover - trivial stub
        return None

    def close(self) -> None:  # pragma: no cover - trivial stub
        return None


log = logging.getLogger(__name__)


class BasculaAppTk:
    """UI controller that orchestrates services and views."""

    def __init__(self, root: Optional[tk.Tk] = None, **_: object) -> None:
        _configure_logging()

        if not os.environ.get("BASCULA_UI_THEME"):
            os.environ["BASCULA_UI_THEME"] = "neo"

        self._dev_mode = _truthy(os.environ.get("BASCULA_UI_DEV"))
        self._light_mode = _truthy(os.environ.get("BASCULA_UI_LIGHT"))

        self.ids: Dict[str, tk.Widget] = {}
        self._image_cache: Dict[str, tk.PhotoImage] = {}

        self.log = logging.getLogger("bascula.ui.app")

        if root is None:
            root = tk.Tk()
        apply_kiosk_window_prefs(root)

        try:
            fullscreen = bool(root.attributes("-fullscreen"))
        except Exception:
            fullscreen = False
        try:
            override_flag = bool(root.overrideredirect())
        except Exception:
            override_flag = False

        self.log.info(
            "Kiosk startup state: fullscreen=%s overrideredirect=%s strict=%s hard=%s debug=%s",
            fullscreen,
            override_flag,
            os.environ.get("BASCULA_KIOSK_STRICT", ""),
            os.environ.get("BASCULA_KIOSK_HARD", ""),
            os.environ.get("BASCULA_DEBUG_KIOSK", ""),
        )

        self.shell = AppShell(root=root)
        self.root = self.shell.root
        self.events: "queue.Queue[tuple[str, dict]]" = queue.Queue()

        self._register_topbar_widgets()
        self._apply_dev_shortcuts()

        heartbeat_file = (os.environ.get("BASCULA_HEARTBEAT_FILE") or "/run/bascula/heartbeat").strip()
        legacy_heartbeat = (os.environ.get("BASCULA_LEGACY_HEARTBEAT_FILE") or "/run/bascula.alive").strip()
        interval_raw = os.environ.get("BASCULA_HEARTBEAT_INTERVAL_MS", "5000")
        try:
            interval_ms = int(interval_raw)
        except (TypeError, ValueError):  # pragma: no cover - defensive parsing
            interval_ms = 5000
        if interval_ms < 1000:
            interval_ms = 1000
        self._heartbeat_interval_ms = interval_ms
        self._heartbeat_job: Optional[str] = None
        self._heartbeat_path: Optional[Path] = None
        self._legacy_heartbeat_path: Optional[Path] = None
        if not self._light_mode:
            if heartbeat_file:
                self._heartbeat_path = Path(heartbeat_file).expanduser()
            if legacy_heartbeat and legacy_heartbeat != heartbeat_file:
                self._legacy_heartbeat_path = Path(legacy_heartbeat).expanduser()
            if self._heartbeat_path is not None:
                self._touch_heartbeat_file(self._heartbeat_path)
                if (
                    self._legacy_heartbeat_path is not None
                    and self._legacy_heartbeat_path != self._heartbeat_path
                ):
                    self._touch_heartbeat_file(self._legacy_heartbeat_path)

        self._cfg = self._load_app_config()
        self._ui_cfg_path = UI_CONFIG_PATH
        self._ui_cfg = load_ui_config(self._ui_cfg_path)
        self._mascota_enabled = bool(self._ui_cfg.get("show_mascota", False))
        self._mascota_container: Optional[tk.Frame] = None
        self.mascota: Optional[tk.Widget] = None
        self.audio = None

        self.scale_cfg = self._load_scale_cfg()
        port = os.environ.get("BASCULA_DEVICE", self.scale_cfg.get("port", "/dev/serial0"))
        decimals = int(self.scale_cfg.get("decimals", 0) or 0)
        density = float(self.scale_cfg.get("density", 1.0) or 1.0)

        if self._light_mode:
            self.scale = _LightScale(decimals=decimals, density=density)
        else:
            try:
                self.scale = ScaleService(port=port, baud=115200, decimals=decimals, density=density)
            except Exception:
                self.scale = ScaleService(port="__dummy__", decimals=decimals, density=density)

        if getattr(self.scale, "simulated", False):
            self.shell.notify("Modo simulado")

        if self._light_mode:
            self.camera = None
        elif CameraService is not None:  # pragma: no branch - simple optional wiring
            try:
                self.camera = CameraService()
            except Exception:  # pragma: no cover - hardware optional
                self.camera = None
        else:  # pragma: no cover - optional dependency missing
            self.camera = None

        if self._light_mode:
            self.tts = _NoOpTTS()
        elif PiperTTS is not None:  # pragma: no branch - simple optional wiring
            try:
                self.tts = PiperTTS()
            except Exception:  # pragma: no cover - optional dependency
                self.tts = _NoOpTTS()
        else:
            self.tts = _NoOpTTS()

        self.nightscout: Optional[object]
        if self._light_mode:
            self.nightscout = None
        elif NightscoutClient is not None:  # pragma: no cover - optional wiring
            try:
                self.nightscout = NightscoutClient()
            except Exception:
                self.nightscout = None
        else:
            self.nightscout = None

        self.home = HomeView(self.shell.content, controller=self)
        self.home.pack(fill="both", expand=True)

        self._timer_state = "idle"
        self._timer_controller = TimerController(
            self.root,
            audio_getter=lambda: getattr(self, "audio", None),
            tts_getter=lambda: getattr(self, "tts", None),
        )
        self._timer_controller.add_listener(self._on_timer_state)
        self._timer_overlay: Optional[TimerOverlay] = None

        self._food_scanner: Optional[FoodScannerView] = None

        self._ns_last_zone: Optional[str] = None
        self._ns_low_active = False
        self._protocol_1515: Optional[Protocol1515Overlay] = None

        self.shell.bind_action("timer", self.open_timer)
        self.shell.bind_action("settings", self.open_settings)
        self.shell.bind_action("wifi", self.open_network)
        self.shell.bind_action("speaker", self.toggle_tts)

        self.home.on_tare = self.perform_tare
        self.home.on_zero = self.perform_zero
        self.home.on_toggle_units = self.toggle_units
        self.home.on_open_food = self.open_food_scanner
        self.home.on_open_recipes = self.open_recipes
        self.home.on_open_timer = self.open_timer
        self.home.on_open_settings = self.open_settings
        self.home.on_set_decimals = self.set_decimals
        self.home.set_decimals(getattr(self.scale, "decimals", 0))

        self._alive = True
        self._reader_thread: Optional[threading.Thread] = None
        self.root.after(100, self._ui_tick)
        if not self._light_mode:
            self._start_scale_reader()

        self._patch_shell_notify()
        self._apply_mascota_visibility()
        if not self._light_mode:
            self._start_heartbeat()

        if self.nightscout is not None:  # pragma: no branch - optional wiring
            try:
                self.nightscout.add_listener(self._on_nightscout_update)
            except Exception:
                log.debug("Nightscout listener no disponible", exc_info=True)

    # ------------------------------------------------------------------
    def _apply_dev_shortcuts(self) -> None:
        if self._dev_mode:
            def _close_app(_event: tk.Event) -> None:
                try:
                    self.destroy()
                finally:
                    try:
                        self.root.quit()
                    except Exception:
                        pass

            self.root.bind("<Escape>", _close_app, add="+")
        else:
            self.root.bind("<Escape>", lambda _e: "break", add="+")

    def _register_topbar_widgets(self) -> None:
        mapping = {
            "wifi": "topbar_wifi",
            "speaker": "topbar_speaker",
            "bg": "topbar_bg",
            "timer": "topbar_timer",
            "notif": "topbar_notif",
        }
        for icon_key, widget_name in mapping.items():
            widget = self.shell.get_icon_widget(icon_key)
            if widget is None:
                continue
            setattr(widget, "name", widget_name)
            self.ids[widget_name] = widget

    def register_widget(self, name: str, widget: tk.Widget) -> None:
        if not name or widget is None:
            return
        setattr(widget, "name", name)
        self.ids[name] = widget

    def icon_path(self, filename: str) -> Path:
        candidate = ICON_DIR / filename
        if candidate.exists():
            return candidate
        fallback = ICON_DIR / "topbar" / filename
        return fallback if fallback.exists() else candidate

    def make_icon_button(
        self,
        parent: tk.Misc,
        icon_path: Optional[os.PathLike[str] | str],
        text: str,
        *,
        name: str,
        command: Optional[Callable[[], None]] = None,
        **grid: object,
    ) -> tk.Button:
        image: Optional[tk.PhotoImage] = None
        icon_name: Optional[str] = None
        if icon_path:
            candidate = Path(icon_path)
            if not candidate.exists():
                candidate = self.icon_path(candidate.name)
            icon_name = candidate.stem
        if not icon_name and name.startswith("btn_"):
            icon_name = name.replace("btn_", "")
        if icon_name:
            image = load_icon(icon_name, 32)

        button = tk.Button(
            parent,
            text=text,
            image=image,
            compound="top",
            font=FONTS["btn"],
            fg=COLORS["fg"],
            bg=COLORS.get("surface", COLORS["bg"]),
            activebackground=COLORS["accent"],
            activeforeground=COLORS["bg"],
            relief="flat",
            highlightthickness=1,
            highlightbackground=COLORS["accent"],
            bd=1,
            padx=SPACING["md"],
            pady=SPACING["md"],
            command=command,
        )
        button.configure(anchor="center")
        if image is not None:
            self._image_cache[name] = image
            button.image = image  # type: ignore[attr-defined]
            button.configure(image=image, compound="top", text=text)
        else:
            button.configure(image="", text=text, compound="center")
        button.configure(cursor="hand2")
        self.register_widget(name, button)

        def _normalize_padding(value: object) -> object:
            if isinstance(value, tuple):
                normalized = []
                for item in value:
                    try:
                        normalized.append(max(SPACING["sm"], int(item)))
                    except Exception:
                        normalized.append(SPACING["sm"])
                return tuple(normalized)
            try:
                numeric = int(value)  # type: ignore[arg-type]
            except Exception:
                numeric = SPACING["sm"]
            return max(SPACING["sm"], numeric)

        grid_options = dict(grid)
        grid_options["padx"] = _normalize_padding(grid_options.get("padx", SPACING["sm"]))
        grid_options["pady"] = _normalize_padding(grid_options.get("pady", SPACING["sm"]))
        if "sticky" not in grid_options:
            grid_options["sticky"] = "nsew"
        button.grid(**grid_options)
        return button

    # ------------------------------------------------------------------
    def _load_scale_cfg(self) -> dict:
        try:
            import tomllib

            config_path = CFG_DIR / "scale.toml"
            if config_path.exists():
                return tomllib.loads(config_path.read_text())
        except Exception:  # pragma: no cover - configuration optional
            return {}
        return {}

    def _start_scale_reader(self) -> None:
        def _reader() -> None:
            last_value: Optional[float] = None
            last_stable: Optional[bool] = None
            while self._alive:
                try:
                    weight = self.scale.net_weight
                    stable = bool(getattr(self.scale, "stable", False))
                except Exception:
                    weight = 0.0
                    stable = False
                if last_value is None or weight != last_value or stable != last_stable:
                    self.events.put(("weight", {"g": weight, "stable": stable}))
                    last_value = weight
                    last_stable = stable
                time.sleep(0.1)

        self._reader_thread = threading.Thread(target=_reader, name="ScaleReader", daemon=True)
        self._reader_thread.start()

    def _start_heartbeat(self) -> None:
        if self._heartbeat_path is None or self._heartbeat_interval_ms <= 0:
            return
        try:
            self.root.after(0, self._emit_heartbeat)
        except Exception:  # pragma: no cover - Tk fallback
            log.debug("No se pudo programar heartbeat inicial", exc_info=True)

    def _emit_heartbeat(self) -> None:
        if not self._alive:
            return
        self._touch_heartbeat_file(self._heartbeat_path)
        if (
            self._legacy_heartbeat_path is not None
            and self._legacy_heartbeat_path != self._heartbeat_path
        ):
            self._touch_heartbeat_file(self._legacy_heartbeat_path)
        try:
            self._heartbeat_job = self.root.after(self._heartbeat_interval_ms, self._emit_heartbeat)
        except Exception:  # pragma: no cover - Tk fallback
            self._heartbeat_job = None
            log.debug("No se pudo programar siguiente heartbeat", exc_info=True)

    def _touch_heartbeat_file(self, path: Optional[Path]) -> None:
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        except Exception:  # pragma: no cover - filesystem errors
            log.debug("No se pudo actualizar heartbeat %s", path, exc_info=True)

    def _patch_shell_notify(self) -> None:
        original_notify = self.shell.notify

        def _wrapped(shell_self: AppShell, message: str, duration_ms: int = 4000) -> None:
            original_notify(message, duration_ms)
            if message:
                self._handle_notification(message)

        self.shell.notify = types.MethodType(_wrapped, self.shell)

    def _handle_notification(self, message: str) -> None:
        if not self._mascota_enabled:
            return
        try:
            if self.mascota and hasattr(self.mascota, "speak"):
                self.mascota.speak()
        except Exception:
            pass
        tts = getattr(self, "tts", None)
        if tts is not None:
            try:
                tts.speak(message)
            except Exception:
                pass

    def _apply_mascota_visibility(self) -> None:
        if self._mascota_enabled:
            self._ensure_mascota_widget()
        else:
            self._remove_mascota_widget()

    def _ensure_mascota_widget(self) -> None:
        if self.mascota is not None and getattr(self.mascota, "winfo_exists", lambda: False)():
            return
        container = tk.Frame(self.root, bg=COLORS.get("bg", "black"))
        container.place(relx=1.0, rely=1.0, anchor="se", x=-16, y=-16)
        try:
            from .widgets_mascota import MiniMascotaAvatar

            widget = MiniMascotaAvatar(container, size=50, bg=COLORS.get("bg", "black"))
        except Exception:
            widget = tk.Canvas(container, width=50, height=50, highlightthickness=0, bg=COLORS.get("bg", "black"))
            widget.create_oval(6, 6, 44, 44, fill=COLORS.get("primary", "#00d4aa"), outline="")
        widget.pack()
        self._mascota_container = container
        self.mascota = widget

    def _remove_mascota_widget(self) -> None:
        widget = self.mascota
        self.mascota = None
        if widget is not None:
            try:
                widget.destroy()
            except Exception:
                pass
        container = self._mascota_container
        self._mascota_container = None
        if container is not None:
            try:
                container.destroy()
            except Exception:
                pass

    def _load_app_config(self) -> dict:
        try:
            return dict(load_main_config())
        except Exception:
            return {}

    def _on_nightscout_update(self, payload: Dict[str, object]) -> None:
        try:
            self.events.put(("nightscout_bg", dict(payload)))
        except Exception:
            log.debug("No se pudo encolar BG", exc_info=True)

    def _apply_nightscout_update(self, payload: Dict[str, object]) -> None:
        mgdl = self._to_int(payload.get("mgdl"))
        direction = str(payload.get("direction") or "").strip()
        text = self._format_glucose_text(mgdl, direction)
        color = self._color_for_glucose(mgdl)
        self.shell.set_glucose_status(text, color)

        cfg_raw = payload.get("config")
        cfg = dict(cfg_raw) if isinstance(cfg_raw, dict) else {}
        self._handle_glucose_alarm(mgdl, cfg)
        self._handle_protocol_1515(mgdl, cfg)

    def _ui_tick(self) -> None:
        try:
            while True:
                topic, data = self.events.get_nowait()
                if topic == "weight":
                    try:
                        grams = float(data.get("g", 0.0))
                        stable = bool(data.get("stable", False))
                    except (TypeError, ValueError):  # pragma: no cover - defensive
                        continue
                    self.home.update_weight(grams, stable)
                elif topic == "nightscout_bg":
                    try:
                        self._apply_nightscout_update(dict(data))
                    except Exception:
                        log.debug("No se pudo aplicar BG", exc_info=True)
        except queue.Empty:
            pass
        if self._alive:
            self.root.after(100, self._ui_tick)

    def _format_glucose_text(self, mgdl: Optional[int], direction: str) -> str:
        if mgdl is None:
            return "—"
        arrow = self._arrow_for_direction(direction)
        return f"{mgdl} mg/dL {arrow}".strip()

    @staticmethod
    def _arrow_for_direction(direction: str) -> str:
        mapping = {
            "DoubleUp": "↑↑",
            "SingleUp": "↑",
            "FortyFiveUp": "↗",
            "Flat": "→",
            "FortyFiveDown": "↘",
            "SingleDown": "↓",
            "DoubleDown": "↓↓",
            "NONE": "→",
            "NOT COMPUTED": "→",
        }
        key = (direction or "").strip()
        return mapping.get(key, mapping.get(key.title(), ""))

    def _color_for_glucose(self, mgdl: Optional[int]) -> str:
        if mgdl is None:
            return COLORS.get("muted", "#99a7b3")
        if mgdl < 70 or mgdl > 250:
            return COLORS.get("danger", "#ff5566")
        if 70 <= mgdl <= 180:
            return "#22c55e"
        return "#facc15"

    def _handle_glucose_alarm(self, mgdl: Optional[int], cfg: Dict[str, object]) -> None:
        low = self._to_int(cfg.get("low_threshold")) or 70
        high = self._to_int(cfg.get("high_threshold")) or 180
        if mgdl is None:
            zone = "unknown"
        elif mgdl < low:
            zone = "low"
        elif mgdl > high:
            zone = "high"
        else:
            zone = "ok"

        alarms_enabled = bool(cfg.get("alarms_enabled", True))
        announce = bool(cfg.get("announce_on_alarm", True))
        if (
            alarms_enabled
            and zone in {"low", "high"}
            and zone != self._ns_last_zone
            and mgdl is not None
        ):
            message = "Glucosa baja" if zone == "low" else "Glucosa alta"
            self.shell.notify(f"{message}: {mgdl} mg/dL", duration_ms=6000)
            if announce:
                try:
                    self.tts.speak(f"{message}. {mgdl} mg por decilitro")
                except Exception:
                    pass

        self._ns_last_zone = zone

    def _handle_protocol_1515(self, mgdl: Optional[int], cfg: Dict[str, object]) -> None:
        enabled = bool(cfg.get("enable_1515", True))
        if not enabled:
            self._ns_low_active = False
            return
        if mgdl is not None and mgdl < 70:
            if not self._ns_low_active:
                overlay = self._ensure_1515_overlay()
                overlay.show()
                self.shell.notify("Inicia protocolo 15/15", duration_ms=5000)
            self._ns_low_active = True
        elif mgdl is not None and mgdl >= 90:
            self._ns_low_active = False

    def _ensure_1515_overlay(self) -> Protocol1515Overlay:
        if self._protocol_1515 is None or not self._protocol_1515.winfo_exists():
            self._protocol_1515 = Protocol1515Overlay(self.root, self)
        return self._protocol_1515

    @staticmethod
    def _to_int(value: object) -> Optional[int]:
        try:
            if value is None:
                return None
            return int(round(float(value)))
        except Exception:
            return None

    # ------------------------------------------------------------------
    def perform_tare(self) -> None:
        try:
            self.scale.tare()
            self.tts.speak("Tara aplicada")
        except Exception as exc:  # pragma: no cover - hardware dependent
            self.shell.notify(f"Error tara: {exc}")

    def perform_zero(self) -> None:
        try:
            self.scale.zero()
            self.tts.speak("Cero aplicado")
        except Exception as exc:  # pragma: no cover - hardware dependent
            self.shell.notify(f"Error cero: {exc}")

    def toggle_units(self) -> None:
        try:
            new_units = self.home.toggle_units()
        except Exception as exc:  # pragma: no cover - defensive
            self.shell.notify(f"Error unidades: {exc}")
            return

        if new_units == "ml":
            try:
                import tkinter.simpledialog as simpledialog

                density = simpledialog.askfloat(
                    "Densidad (g/ml)",
                    "Introduce la densidad del ingrediente",
                    initialvalue=self.scale.density,
                    minvalue=0.1,
                )
                if density:
                    self.scale.set_density(float(density))
            except Exception:
                self.shell.notify("No se pudo ajustar la densidad")

    def open_food_scanner(self) -> None:
        try:
            if self._food_scanner and self._food_scanner.winfo_exists():
                self._food_scanner.lift()
                return
        except Exception:
            self._food_scanner = None

        try:
            window = FoodScannerView(self, scale=self.scale, camera=self.camera, tts=self.tts)

            def _on_destroy(event) -> None:
                if getattr(event, "widget", None) is window:
                    self._food_scanner = None

            window.bind("<Destroy>", _on_destroy)
            self._food_scanner = window
        except Exception as exc:
            self.shell.notify(f"No se pudo abrir el escáner: {exc}")

    def open_recipes(self) -> None:
        self.shell.notify("Recetas próximamente")

    def open_timer(self) -> None:
        try:
            if self._timer_overlay is None or not self._timer_overlay.winfo_exists():
                self._timer_overlay = TimerOverlay(self.root, controller=self._timer_controller)
            self._timer_overlay.show()
        except Exception as exc:
            self.shell.notify(f"Temporizador no disponible: {exc}")

    def _on_timer_state(self, seconds: Optional[int], state: str) -> None:
        if seconds is None:
            self.shell.set_timer_state(None, state)
        else:
            self.shell.set_timer_state(self._format_timer(seconds), state)
        if state == "finished" and self._timer_state != "finished":
            self.shell.notify("Temporizador finalizado", duration_ms=6000)
        self._timer_state = state

    @staticmethod
    def _format_timer(seconds: int) -> str:
        total = max(0, int(seconds))
        minutes, remaining = divmod(total, 60)
        return f"{minutes:02d}:{remaining:02d}"

    def open_settings(self) -> None:
        try:
            if not hasattr(self, "_calibration_overlay"):
                self._calibration_overlay = CalibrationOverlay(self.root, scale=self.scale, on_close=lambda: None)
            self._calibration_overlay.show()
        except Exception as exc:
            self.shell.notify(f"Calibración no disponible: {exc}")

    def set_decimals(self, decimals: int) -> None:
        try:
            updated = self.scale.set_decimals(decimals)
            self.home.set_decimals(updated)
        except Exception as exc:  # pragma: no cover - defensive
            self.shell.notify(f"Error decimales: {exc}")
            try:
                self.home.set_decimals(getattr(self.scale, "decimals", 0))
            except Exception:
                pass

    def open_network(self) -> None:
        self.shell.notify("Red/Wi-Fi en mini-web")

    def toggle_tts(self) -> None:
        self.shell.notify("Voz Piper activada/desactivada")

    # ------------------------------------------------------------------
    def get_cfg(self) -> dict:
        return self._cfg

    def save_cfg(self) -> None:
        try:
            save_main_config(self._cfg)
        except Exception:
            log.debug("No se pudo guardar config.json", exc_info=True)

    def get_ui_cfg(self) -> dict:
        return dict(self._ui_cfg)

    def set_mascota_enabled(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if enabled == self._mascota_enabled:
            return
        self._mascota_enabled = enabled
        self._ui_cfg["show_mascota"] = enabled
        dump_ui_config(self._ui_cfg, self._ui_cfg_path)
        self._apply_mascota_visibility()
        if enabled and getattr(self, "mascota", None) and hasattr(self.mascota, "speak"):
            try:
                self.mascota.speak(600)
            except Exception:
                pass

    def get_audio(self):
        return getattr(self, "audio", None)

    # ------------------------------------------------------------------
    def run(self) -> None:
        self.shell.run()

    def destroy(self) -> None:
        self._alive = False
        if self._heartbeat_job is not None:
            try:
                self.root.after_cancel(self._heartbeat_job)
            except Exception:  # pragma: no cover - Tk fallback
                pass
            self._heartbeat_job = None
        if self._reader_thread and self._reader_thread.is_alive():
            self._reader_thread.join(timeout=0.5)
        try:
            self.scale.stop()
        except Exception:
            try:
                self.scale.close()  # type: ignore[attr-defined]
            except Exception:
                pass
        try:
            if getattr(self, "nightscout", None) and hasattr(self.nightscout, "stop"):
                self.nightscout.stop()  # type: ignore[call-arg]
        except Exception:
            pass
        try:
            self.shell.destroy()
        except Exception:
            pass

    def cleanup(self) -> None:  # pragma: no cover - compatibility hook
        self.destroy()


class _NoOpTTS:
    def speak(self, *_args: object, **_kwargs: object) -> None:
        return None


BasculaApp = BasculaAppTk


def main() -> None:
    app = BasculaAppTk()
    app.run()


__all__ = ["BasculaApp", "BasculaAppTk", "main"]

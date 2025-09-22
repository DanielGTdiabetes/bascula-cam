"""Tk application controller wiring services and views."""
from __future__ import annotations

import logging
import os
import queue
import threading
import time
from pathlib import Path
from typing import Dict, Optional

import tkinter as tk

from .app_shell import AppShell
from .views.home import HomeView
from .views.food_scanner import FoodScannerView
from .overlays.calibration import CalibrationOverlay
from .overlay_1515 import Protocol1515Overlay
from .overlays.timer import TimerController, TimerOverlay
from .theme_neo import COLORS
from ..services.scale import ScaleService

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


log = logging.getLogger(__name__)


class BasculaAppTk:
    """UI controller that orchestrates services and views."""

    def __init__(self, root: Optional[tk.Tk] = None, **_: object) -> None:
        self.shell = AppShell(root=root)
        self.root = self.shell.root
        self.events: "queue.Queue[tuple[str, dict]]" = queue.Queue()

        self.scale_cfg = self._load_scale_cfg()
        port = os.environ.get("BASCULA_DEVICE", self.scale_cfg.get("port", "/dev/serial0"))
        decimals = int(self.scale_cfg.get("decimals", 0) or 0)
        density = float(self.scale_cfg.get("density", 1.0) or 1.0)

        try:
            self.scale = ScaleService(port=port, baud=115200, decimals=decimals, density=density)
        except Exception:
            self.scale = ScaleService(port="__dummy__", decimals=decimals, density=density)

        if getattr(self.scale, "simulated", False):
            self.shell.notify("Modo simulado")

        if CameraService is not None:  # pragma: no branch - simple optional wiring
            try:
                self.camera = CameraService()
            except Exception:  # pragma: no cover - hardware optional
                self.camera = None
        else:  # pragma: no cover - optional dependency missing
            self.camera = None

        if PiperTTS is not None:  # pragma: no branch - simple optional wiring
            try:
                self.tts = PiperTTS()
            except Exception:  # pragma: no cover - optional dependency
                self.tts = _NoOpTTS()
        else:
            self.tts = _NoOpTTS()

        self.nightscout: Optional[object]
        if NightscoutClient is not None:  # pragma: no cover - optional wiring
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
        self._start_scale_reader()

        if self.nightscout is not None:  # pragma: no branch - optional wiring
            try:
                self.nightscout.add_listener(self._on_nightscout_update)
            except Exception:
                log.debug("Nightscout listener no disponible", exc_info=True)

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
    def run(self) -> None:
        self.shell.run()

    def destroy(self) -> None:
        self._alive = False
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

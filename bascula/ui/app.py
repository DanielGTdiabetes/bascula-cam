"""Tk application controller wiring services and views."""
from __future__ import annotations

import os
import queue
import threading
import time
from pathlib import Path
from typing import Optional

import tkinter as tk

from .app_shell import AppShell
from .views.home import HomeView
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

        self._alive = True
        self._reader_thread: Optional[threading.Thread] = None
        self.root.after(100, self._ui_tick)
        self._start_scale_reader()

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
            while self._alive:
                try:
                    weight = self.scale.net_weight
                except Exception:
                    weight = 0.0
                if last_value is None or weight != last_value:
                    self.events.put(("weight", {"g": weight}))
                    last_value = weight
                time.sleep(0.1)

        self._reader_thread = threading.Thread(target=_reader, name="ScaleReader", daemon=True)
        self._reader_thread.start()

    def _ui_tick(self) -> None:
        try:
            while True:
                topic, data = self.events.get_nowait()
                if topic == "weight":
                    try:
                        grams = float(data["g"])
                    except (KeyError, TypeError, ValueError):  # pragma: no cover - defensive
                        continue
                    self.home.set_weight_g(grams)
        except queue.Empty:
            pass
        if self._alive:
            self.root.after(100, self._ui_tick)

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
            self.home.toggle_units()
        except Exception as exc:  # pragma: no cover - defensive
            self.shell.notify(f"Error unidades: {exc}")

    def open_food_scanner(self) -> None:
        try:
            from .overlay_scanner import OverlayScanner  # type: ignore

            OverlayScanner(self.root, scale=self.scale, camera=self.camera, tts=self.tts)
        except Exception:
            self.shell.notify("Escáner de alimentos no disponible aún")

    def open_recipes(self) -> None:
        self.shell.notify("Recetas próximamente")

    def open_timer(self) -> None:
        try:
            from .overlay_timer import TimerOverlay

            TimerOverlay(self.root, on_done=lambda: self.tts.speak("Temporizador finalizado"))
        except Exception:
            self.shell.notify("Temporizador no disponible")

    def open_settings(self) -> None:
        self.shell.notify("Ajustes próximamente")

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

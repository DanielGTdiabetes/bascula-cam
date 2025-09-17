"""High level Tkinter application used by the Báscula Cam kiosk."""

from __future__ import annotations

import logging
from importlib import import_module
import tkinter as tk
from typing import Dict, Optional, Type

from bascula.config.theme import apply_theme
from bascula.services.event_bus import EventBus
from bascula.services.scale import ScaleService
from bascula.services.tare_manager import TareManager
from bascula.utils import MovingAverage, load_config, save_config
from bascula.ui.widgets import TopBar, COL_BG
from bascula.ui.screens import HomeScreen, ScaleScreen, SettingsScreen

try:  # Optional – audio is not critical during development/testing
    from bascula.services.audio import AudioService
except Exception:  # pragma: no cover - missing optional dependency
    AudioService = None  # type: ignore


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

        self.root = root if root is not None else tk.Tk()
        self.root.title("Báscula Cam")
        self.root.minsize(800, 480)

        desired_theme = self.cfg.get("ui_theme", theme)
        apply_theme(self.root, desired_theme)

        self.root.configure(bg=COL_BG)
        self.root.geometry("1024x600")
        self.root.bind("<Escape>", lambda _evt: self.root.quit())
        self.root.bind("<F5>", lambda _evt: self.show_screen("home"))

        # Reactive variables shared by multiple screens
        self.weight_text = tk.StringVar(value="0 g")
        self.stability_text = tk.StringVar(value="Sin lectura")
        self.weight_history: list[dict[str, object]] = []

        # Build UI chrome
        self.topbar = TopBar(self.root, self)
        self.topbar.pack(fill=tk.X)

        self.container = tk.Frame(self.root, bg=COL_BG)
        self.container.pack(fill=tk.BOTH, expand=True)

        # Screen registry
        self.screens: Dict[str, tk.Frame] = {}
        for screen_cls in (HomeScreen, ScaleScreen, SettingsScreen):
            self._register_screen(screen_cls)

        optional_screens = [
            ("history", "bascula.ui.history_screen", "HistoryScreen"),
            ("focus", "bascula.ui.focus_screen", "FocusScreen"),
            ("nightscout", "bascula.ui.screens_nightscout", "NightscoutScreen"),
            ("wifi", "bascula.ui.screens_wifi", "WifiScreen"),
            ("apikey", "bascula.ui.screens_apikey", "ApiKeyScreen"),
            ("diabetes", "bascula.ui.screens_diabetes", "DiabetesSettingsScreen"),
        ]
        for key, module_name, class_name in optional_screens:
            self._register_optional_screen(key, module_name, class_name)

        try:
            self.topbar.refresh_more_menu()
        except Exception:
            pass

        self.current_screen = None
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

        self.root.after(300, self._update_weight_loop)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    # ------------------------------------------------------------------ Lifecycle
    def run(self) -> None:
        self.root.mainloop()

    def close(self) -> None:
        try:
            if self.reader:
                self.reader.stop()
        finally:
            self.root.destroy()

    # ------------------------------------------------------------------ Navigation
    def show_screen(self, name: str) -> None:
        screen = self.screens.get(name)
        if screen is None:
            self.logger.warning("Pantalla '%s' no encontrada", name)
            return
        if self.current_screen is screen:
            return
        if self.current_screen is not None:
            try:
                self.current_screen.on_hide()
            except Exception:
                pass
            self.current_screen.pack_forget()
        screen.pack(fill=tk.BOTH, expand=True)
        try:
            screen.on_show()
        except Exception:
            pass
        self.current_screen = screen
        try:
            self.topbar.set_active(name)
        except Exception:
            pass

    def _register_screen(self, screen_cls: Type[tk.Frame], key: Optional[str] = None) -> None:
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
        self.screens[name] = screen

    def _register_optional_screen(self, key: str, module_name: str, class_name: str) -> None:
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
        self._register_screen(screen_cls, key)

    # ------------------------------------------------------------------ Services API
    def get_cfg(self) -> dict:
        return self.cfg

    def save_cfg(self) -> None:
        save_config(self.cfg)
        try:
            if "ui_theme" in self.cfg:
                apply_theme(self.root, self.cfg.get("ui_theme", "modern"))
        except Exception:
            self.logger.exception("No se pudo aplicar el tema tras guardar la configuración")

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

    # ------------------------------------------------------------------ Actions
    def perform_tare(self) -> None:
        raw = self.reader.get_weight() if self.reader else 0.0
        self.tare.set_tare(raw)
        self._last_captured = 0.0
        self.messenger.show("Tara aplicada", icon="⚖️")

    def perform_zero(self) -> None:
        self.tare.clear_tare()
        self._last_captured = 0.0
        self.messenger.show("Tara reiniciada", icon="🧮")

    def capture_weight(self) -> None:
        weight = self.get_latest_weight()
        if weight <= 0:
            self.messenger.show("No hay peso estable para capturar", kind="warning", icon="ℹ️")
            return
        self._append_history(weight, manual=True)
        self.event_bus.publish("WEIGHT_CAPTURED", weight)

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


# Backwards compatibility export -------------------------------------------------
BasculaApp = BasculaAppTk


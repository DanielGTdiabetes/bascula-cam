"""Main Tk application controller for Bascula."""
from __future__ import annotations

import logging
import os
import tkinter as tk
from tkinter import messagebox
from typing import Optional

from ..config.settings import Settings
from ..runtime import HeartbeatWriter
from ..services.audio import AudioService
from ..services.nightscout import NightscoutService
from ..services.nutrition import NutritionService
from ..services.scale import ScaleService
from .screens import FoodsScreen, HomeScreen, RecipesScreen, SettingsScreen
from .windowing import apply_kiosk_to_toplevel, apply_kiosk_window_prefs

log = logging.getLogger(__name__)


class BasculaApp:
    """Application entry point responsible for wiring UI and services."""

    def __init__(self) -> None:
        self.root = tk.Tk()
        apply_kiosk_window_prefs(self.root)
        self.root.title("Báscula Cam")
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)

        self.settings = Settings.load()
        self.audio_service = AudioService(
            audio_device=self.settings.audio.audio_device,
            volume=self.settings.general.volume,
        )
        self.audio_service.set_enabled(self.settings.general.sound_enabled)

        self.scale_service = ScaleService(self.settings.scale)
        self.nutrition_service = NutritionService()
        self.nightscout_service = NightscoutService(self.settings.diabetes)

        self.scale_service.subscribe(self._on_weight)
        self.scale_service.start()
        self.nightscout_service.set_listener(self._on_glucose)
        self.nightscout_service.start()

        self.heartbeat = HeartbeatWriter()
        self.heartbeat.start()

        self._timer_seconds = 0
        self._timer_job: int | None = None

        self._build_toolbar()
        self._build_state_vars()
        self._build_router()
        self._apply_debug_shortcuts()

        self.navigate("home")

    # ------------------------------------------------------------------
    def _build_toolbar(self) -> None:
        self.toolbar = tk.Frame(self.root, bg="white", bd=0, relief="flat")
        self.toolbar.pack(fill="x")

        self.glucose_var = tk.StringVar(value="Glucosa --")
        self.glucose_label = tk.Label(
            self.toolbar,
            textvariable=self.glucose_var,
            font=("DejaVu Sans", 14, "bold"),
            fg="#0050d0",
            bg="white",
        )
        self.glucose_label.pack(side="left", padx=16, pady=12)

        self.timer_var = tk.StringVar(value="")
        self.timer_label = tk.Label(
            self.toolbar,
            textvariable=self.timer_var,
            font=("DejaVu Sans", 14, "bold"),
            fg="#1f2430",
            bg="white",
        )
        self.timer_label.pack(side="left", padx=16)

        self.sound_button = tk.Button(
            self.toolbar,
            text="🔊" if self.settings.general.sound_enabled else "🔇",
            command=self.toggle_sound,
            bg="white",
            fg="#1f2430",
            bd=0,
            relief="flat",
            font=("DejaVu Sans", 16),
            takefocus=0,
        )
        self.sound_button.pack(side="left", padx=10)

        tk.Button(
            self.toolbar,
            text="⚙️",
            command=lambda: self.navigate("settings"),
            bg="white",
            fg="#1f2430",
            bd=0,
            relief="flat",
            font=("DejaVu Sans", 18),
            takefocus=0,
        ).pack(side="right", padx=16)

    def _build_state_vars(self) -> None:
        self.general_sound_var = tk.BooleanVar(value=self.settings.general.sound_enabled)
        self.general_volume_var = tk.IntVar(value=self.settings.general.volume)
        self.general_sound_var.trace_add("write", lambda *_: self._sync_sound())
        self.general_volume_var.trace_add("write", lambda *_: self.audio_service.set_volume(self.general_volume_var.get()))

        self.scale_calibration_var = tk.DoubleVar(value=self.settings.scale.calibration_factor)
        self.scale_density_var = tk.DoubleVar(value=self.settings.scale.ml_factor)
        self.scale_calibration_var.trace_add("write", lambda *_: self.scale_service.set_calibration_factor(self.scale_calibration_var.get()))
        self.scale_density_var.trace_add("write", lambda *_: self.scale_service.set_ml_factor(self.scale_density_var.get()))

        self.diabetes_enabled_var = tk.BooleanVar(value=self.settings.diabetes.diabetes_enabled)
        self.diabetes_url_var = tk.StringVar(value=self.settings.diabetes.ns_url)
        self.diabetes_token_var = tk.StringVar(value=self.settings.diabetes.ns_token)
        self.miniweb_enabled_var = tk.BooleanVar(value=self.settings.network.miniweb_enabled)

    def _build_router(self) -> None:
        self.container = tk.Frame(self.root, bg="white")
        self.container.pack(fill="both", expand=True)

        self.screens = {
            "home": HomeScreen(self.container, self),
            "alimentos": FoodsScreen(self.container, self),
            "recetas": RecipesScreen(self.container, self),
            "settings": SettingsScreen(self.container, self),
        }
        for screen in self.screens.values():
            screen.place(relx=0, rely=0, relwidth=1, relheight=1)

    def _apply_debug_shortcuts(self) -> None:
        if os.getenv("BASCULA_DEBUG_KIOSK") == "1":
            self.root.bind("<F8>", lambda _e: self.navigate("home"))
            self.root.bind("<F9>", lambda _e: self.navigate("home"))
            self.root.bind("<F10>", lambda _e: self.navigate("settings"))

    # ------------------------------------------------------------------
    def navigate(self, route: str) -> None:
        screen = self.screens.get(route)
        if not screen:
            log.warning("Pantalla desconocida: %s", route)
            return
        screen.lift()
        log.info("Pantalla activa: %s", route)

    # ------------------------------------------------------------------
    def _on_weight(self, value: Optional[float], stable: bool, unit: str) -> None:
        self.root.after(0, lambda: self.screens["home"].update_weight(value, stable, unit))

    def _on_glucose(self, reading) -> None:
        self.root.after(0, lambda: self.glucose_var.set(f"Glucosa {reading.glucose_mgdl} {reading.direction}"))

    # ------------------------------------------------------------------
    def toggle_sound(self) -> None:
        enabled = not self.general_sound_var.get()
        self.general_sound_var.set(enabled)
        self._sync_sound()

    def _sync_sound(self) -> None:
        enabled = self.general_sound_var.get()
        self.audio_service.set_enabled(enabled)
        self.sound_button.configure(text="🔊" if enabled else "🔇")

    # ------------------------------------------------------------------
    def handle_tare(self) -> None:
        self.scale_service.tare()
        self.audio_service.beep_ok()

    def handle_zero(self) -> None:
        self.scale_service.zero()
        self.audio_service.beep_ok()

    def handle_toggle_units(self) -> None:
        mode = self.scale_service.toggle_units()
        messagebox.showinfo("Unidades", f"Modo {mode} activo")

    def handle_timer(self) -> None:
        TimerPopup(self.root, self._start_timer)

    def _start_timer(self, seconds: int) -> None:
        self._timer_seconds = max(0, int(seconds))
        if self._timer_job:
            self.root.after_cancel(self._timer_job)
        if self._timer_seconds == 0:
            self.timer_var.set("")
            return
        self._tick_timer()

    def _tick_timer(self) -> None:
        mins, secs = divmod(self._timer_seconds, 60)
        self.timer_var.set(f"⏱ {mins:02d}:{secs:02d}")
        if self._timer_seconds <= 0:
            if self._timer_job:
                self._timer_job = None
            self.audio_service.beep_alarm()
            self.audio_service.speak("El temporizador ha finalizado")
            self.timer_var.set("")
            return
        self._timer_seconds -= 1
        self._timer_job = self.root.after(1000, self._tick_timer)

    # ------------------------------------------------------------------
    def shutdown(self) -> None:
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
        self.settings.scale.calibration_factor = float(self.scale_calibration_var.get())
        self.settings.scale.ml_factor = float(self.scale_density_var.get())
        self.settings.diabetes.diabetes_enabled = self.diabetes_enabled_var.get()
        self.settings.diabetes.ns_url = self.diabetes_url_var.get()
        self.settings.diabetes.ns_token = self.diabetes_token_var.get()
        self.settings.network.miniweb_enabled = self.miniweb_enabled_var.get()
        self.settings.save()

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


class TimerPopup(tk.Toplevel):
    def __init__(self, master: tk.Misc, callback) -> None:
        super().__init__(master)
        apply_kiosk_to_toplevel(self)
        self.title("Temporizador")
        self.callback = callback
        self.geometry("360x260")
        self.configure(bg="white")

        tk.Label(self, text="Selecciona duración", bg="white", font=("DejaVu Sans", 14, "bold")).pack(pady=12)
        button_frame = tk.Frame(self, bg="white")
        button_frame.pack(pady=10)
        for seconds in (60, 300, 600, 900):
            tk.Button(
                button_frame,
                text=f"{seconds // 60} min",
                command=lambda s=seconds: self._finish(s),
                padx=14,
                pady=10,
            ).pack(side="left", padx=5)

        tk.Label(self, text="Personalizado (min)", bg="white").pack(pady=(20, 4))
        self.entry = tk.Entry(self)
        self.entry.pack()
        tk.Button(self, text="Aceptar", command=self._submit).pack(pady=10)

    def _finish(self, seconds: int) -> None:
        self.callback(seconds)
        self.destroy()

    def _submit(self) -> None:
        try:
            minutes = float(self.entry.get())
        except ValueError:
            messagebox.showerror("Valor inválido", "Introduce un número válido")
            return
        self._finish(int(minutes * 60))


__all__ = ["BasculaApp"]

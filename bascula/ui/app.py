"""Main Tk application controller for Bascula."""
from __future__ import annotations

import inspect
import logging
import os
import tkinter as tk
from pathlib import Path
from tkinter import messagebox
from typing import Callable, Optional

from ..config.settings import ScaleSettings, Settings
from ..runtime import HeartbeatWriter
from ..services.audio import AudioService
from ..services.nightscout import NightscoutService
from ..services.nutrition import NutritionService
from ..services.scale import BackendUnavailable, ScaleService
from .screens import FoodsScreen, HomeScreen, RecipesScreen, SettingsScreen
from .windowing import apply_kiosk_to_toplevel, apply_kiosk_window_prefs

try:  # pragma: no cover - optional import during unit tests
    from .keyboard import NumericKeyPopup
except Exception:  # pragma: no cover - keyboard optional
    NumericKeyPopup = None  # type: ignore

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
        self.root = tk.Tk()
        apply_kiosk_window_prefs(self.root)
        self.root.title("Báscula Cam")
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)

        self.heartbeat = HeartbeatWriter()
        self.heartbeat.start()

        self.settings = Settings.load()
        self.audio_service = AudioService(
            audio_device=self.settings.audio.audio_device,
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

        self._timer_seconds = 0
        self._timer_job: int | None = None
        self._nav_history: list[str] = []
        self._current_route: Optional[str] = None
        self._escape_binding: Optional[str] = None

        self._build_toolbar()
        self._build_state_vars()
        self._build_router()
        self._apply_debug_shortcuts()

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
        self.general_tts_var = tk.BooleanVar(value=self.settings.general.tts_enabled)
        self.voice_model_var = tk.StringVar(value=self.settings.audio.voice_model or "")
        self.general_sound_var.trace_add("write", lambda *_: self._sync_sound())
        self.general_volume_var.trace_add(
            "write", lambda *_: self.audio_service.set_volume(self.general_volume_var.get())
        )
        self.general_tts_var.trace_add(
            "write", lambda *_: self.audio_service.set_tts_enabled(self.general_tts_var.get())
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
        self.miniweb_pin_var = tk.StringVar(value=self.settings.network.miniweb_pin)

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

        try:
            density_value = float(self.scale_density_var.get())
        except (TypeError, ValueError):
            errors.append("densidad ml")
            density_value = self.scale_service.get_ml_factor()
        else:
            applied_ml = self.scale_service.set_ml_factor(density_value)
            self.scale_density_var.set(self._format_float(applied_ml))

        try:
            decimals_value = int(self.scale_decimals_var.get())
        except (TypeError, ValueError):
            errors.append("decimales")
            decimals_value = self.scale_service.get_decimals()
        decimals_applied = self.scale_service.set_decimals(decimals_value)
        self.scale_decimals_var.set(decimals_applied)

        unit_applied = self.scale_service.set_unit(self.scale_unit_var.get())
        self.scale_unit_var.set(unit_applied)

        if errors:
            messagebox.showerror(
                "Valores inválidos",
                "No se pudo actualizar: " + ", ".join(errors),
            )
        else:
            self.audio_service.beep_ok()

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
        self.settings.general.tts_enabled = self.general_tts_var.get()
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
        self.settings.network.miniweb_pin = self.miniweb_pin_var.get()
        self.settings.save()

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
        self.settings.network.miniweb_pin = self.miniweb_pin_var.get()
        self._persist_settings()
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
        self.entry.bind("<Button-1>", self._open_keyboard, add=True)
        btn_row = tk.Frame(self, bg="white")
        btn_row.pack(pady=10)
        tk.Button(btn_row, text="Teclado", command=self._open_keyboard).pack(side="left", padx=6)
        tk.Button(btn_row, text="Aceptar", command=self._submit).pack(side="left", padx=6)

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

    def _open_keyboard(self, _event=None):
        if NumericKeyPopup is None:
            return "break" if _event else None

        def _accept(value: str) -> None:
            clean = value.strip()
            if not clean:
                return
            try:
                int(clean)
            except ValueError:
                return
            self.entry.delete(0, "end")
            self.entry.insert(0, clean)

        NumericKeyPopup(
            self,
            title="Minutos",
            initial=self.entry.get(),
            on_accept=_accept,
            allow_negative=False,
            allow_decimal=False,
        )
        return "break" if _event else None


__all__ = ["BasculaApp"]

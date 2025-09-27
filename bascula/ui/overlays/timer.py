"""Kitchen timer overlay with presets and persistent countdown state."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Callable, Optional, Tuple

from bascula.ui.overlay_base import OverlayBase
from bascula.ui.widgets import (
    COL_ACCENT,
    COL_BORDER,
    COL_CARD,
    COL_DANGER,
    COL_MUTED,
    COL_TEXT,
    FS_BTN_SMALL,
    FS_TEXT,
    FS_TITLE,
)
from bascula.ui.input_helpers import bind_numeric_entry
try:
    from bascula.ui.keyboard import NumericKeyPopup
except Exception:
    NumericKeyPopup = None  # type: ignore
from bascula.ui.ui_config import CONFIG_PATH

MAX_MINUTES = 120
MAX_SECONDS = MAX_MINUTES * 60


def _format_seconds(seconds: int) -> str:
    total = max(0, int(seconds))
    minutes, remaining = divmod(total, 60)
    return f"{minutes:02d}:{remaining:02d}"


def _load_last_seconds(path: Path) -> int:
    try:
        import tomllib

        if path.exists():
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            value = data.get("timer_last_seconds")
            if isinstance(value, (int, float)):
                return int(value)
            if isinstance(value, str) and value.strip():
                return int(float(value.strip()))
    except Exception:
        return 300
    return 300


def _save_last_seconds(path: Path, seconds: int) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        return

    new_line = f"timer_last_seconds = {int(seconds)}"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        lines = []
    except Exception:
        lines = []

    replaced = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        key, _, _ = stripped.partition("=")
        if key.strip() == "timer_last_seconds":
            indent = line[: len(line) - len(line.lstrip())]
            lines[index] = f"{indent}{new_line}"
            replaced = True
            break

    if not replaced:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(new_line)

    try:
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass


class TimerController:
    """Application-wide countdown manager."""

    def __init__(
        self,
        root: tk.Misc,
        *,
        audio_getter: Optional[Callable[[], object]] = None,
        tts_getter: Optional[Callable[[], object]] = None,
        config_path: Path = CONFIG_PATH,
    ) -> None:
        self._root = root
        self._audio_getter = audio_getter
        self._tts_getter = tts_getter
        self._config_path = config_path
        self._remaining: int = 0
        self._state: str = "idle"
        self._tick_job: Optional[str] = None
        self._alarm_job: Optional[str] = None
        self._alarm_ticks: int = 0
        self._alarm_primary = False
        self._listeners: list[Callable[[Optional[int], str], None]] = []
        self._last_seconds = max(60, min(MAX_SECONDS, _load_last_seconds(config_path)))

    # ------------------------------------------------------------------
    def add_listener(
        self,
        callback: Callable[[Optional[int], str], None],
        *,
        fire: bool = True,
    ) -> None:
        if callback in self._listeners:
            return
        self._listeners.append(callback)
        if fire:
            seconds, state = self._current_payload()
            try:
                callback(seconds, state)
            except Exception:
                pass

    def remove_listener(self, callback: Callable[[Optional[int], str], None]) -> None:
        try:
            self._listeners.remove(callback)
        except ValueError:
            pass

    # ------------------------------------------------------------------
    def start(self, seconds: int) -> None:
        seconds = max(1, min(int(seconds), MAX_SECONDS))
        self.cancel(notify=False)
        self._remaining = seconds
        self._state = "running"
        self._last_seconds = seconds
        _save_last_seconds(self._config_path, seconds)
        self._notify(self._remaining, "running")
        self._tick_job = self._root.after(1000, self._tick)

    def cancel(self, *, notify: bool = True) -> None:
        if self._tick_job:
            try:
                self._root.after_cancel(self._tick_job)
            except Exception:
                pass
            self._tick_job = None
        self._stop_alarm()
        self._remaining = 0
        previous_state = self._state
        self._state = "idle"
        if notify and previous_state != "idle":
            self._notify(None, "idle")
        elif notify and previous_state == "idle":
            self._notify(None, "idle")

    # ------------------------------------------------------------------
    def notify_current(self) -> None:
        seconds, state = self._current_payload()
        self._notify(seconds, state)

    # ------------------------------------------------------------------
    def is_running(self) -> bool:
        return self._state == "running"

    @property
    def state(self) -> str:
        return self._state

    @property
    def remaining_seconds(self) -> int:
        return max(0, int(self._remaining))

    @property
    def last_seconds(self) -> int:
        return int(self._last_seconds)

    @property
    def last_minutes(self) -> int:
        seconds = max(0, self._last_seconds)
        minutes = max(1, (seconds + 59) // 60)
        return min(MAX_MINUTES, minutes)

    # ------------------------------------------------------------------
    def _tick(self) -> None:
        self._tick_job = None
        self._remaining -= 1
        if self._remaining <= 0:
            self._remaining = 0
            self._finish()
            return
        self._notify(self._remaining, "running")
        self._tick_job = self._root.after(1000, self._tick)

    def _finish(self) -> None:
        self._state = "finished"
        self._notify(0, "finished")
        self._start_alarm()
        self._speak()

    def _start_alarm(self) -> None:
        self._stop_alarm()
        self._alarm_ticks = 0
        self._alarm_primary = False
        self._alarm_job = self._root.after(0, self._alarm_step)

    def _alarm_step(self) -> None:
        self._alarm_job = None
        self._alarm_ticks += 1
        self._trigger_beep(primary=not self._alarm_primary)
        self._alarm_primary = True
        if self._alarm_ticks < 10:
            self._alarm_job = self._root.after(1000, self._alarm_step)

    def _stop_alarm(self) -> None:
        if self._alarm_job:
            try:
                self._root.after_cancel(self._alarm_job)
            except Exception:
                pass
        self._alarm_job = None
        self._alarm_ticks = 0
        self._alarm_primary = False

    def _trigger_beep(self, *, primary: bool) -> None:
        audio = self._audio_getter() if callable(self._audio_getter) else None
        if primary and audio is not None:
            try:
                getattr(audio, "play_event", lambda *_: None)("timer_done")
                return
            except Exception:
                pass
        try:
            self._root.bell()
        except Exception:
            pass

    def _speak(self) -> None:
        tts = self._tts_getter() if callable(self._tts_getter) else None
        if tts is None:
            return
        try:
            getattr(tts, "speak", lambda *_: None)("Temporizador finalizado")
        except Exception:
            pass

    # ------------------------------------------------------------------
    def _notify(self, seconds: Optional[int], state: str) -> None:
        for callback in list(self._listeners):
            try:
                callback(seconds, state)
            except Exception:
                pass

    def _current_payload(self) -> Tuple[Optional[int], str]:
        if self._state == "running":
            return self._remaining, "running"
        if self._state == "finished":
            return 0, "finished"
        return None, "idle"


class TimerOverlay(OverlayBase):
    """Popup overlay that allows selecting a countdown preset or custom value."""

    def __init__(self, parent: tk.Misc, controller: TimerController, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self.controller = controller
        self._status_var = tk.StringVar()
        self._manual_var = tk.StringVar(value=str(self.controller.last_minutes))
        self._listener = self._handle_timer_update
        self.controller.add_listener(self._listener, fire=False)

        container = self.content()
        container.configure(padx=24, pady=24, bg=COL_CARD)

        title = tk.Label(
            container,
            text="Temporizador",
            bg=COL_CARD,
            fg=COL_TEXT,
            font=("DejaVu Sans", FS_TITLE, "bold"),
        )
        title.pack(pady=(0, 12))

        status = tk.Label(
            container,
            textvariable=self._status_var,
            bg=COL_CARD,
            fg=COL_MUTED,
            font=("DejaVu Sans", FS_TEXT),
        )
        status.pack(pady=(0, 16))

        presets = tk.Frame(container, bg=COL_CARD)
        presets.pack(pady=(0, 18))

        for minutes in (1, 5, 10, 15):
            btn = tk.Button(
                presets,
                text=f"{minutes} min",
                command=lambda m=minutes: self._start_from_preset(m),
                bg=COL_ACCENT,
                fg=COL_TEXT,
                activebackground=COL_ACCENT,
                activeforeground=COL_TEXT,
                bd=0,
                relief="flat",
                font=("DejaVu Sans", FS_BTN_SMALL, "bold"),
                cursor="hand2",
                highlightthickness=0,
            )
            btn.pack(side="left", padx=6)

        custom_frame = tk.Frame(container, bg=COL_CARD)
        custom_frame.pack(pady=(0, 18))

        custom_label = tk.Label(
            custom_frame,
            text="Minutos personalizados",
            bg=COL_CARD,
            fg=COL_TEXT,
            font=("DejaVu Sans", FS_TEXT),
        )
        custom_label.pack()

        entry = tk.Entry(
            custom_frame,
            textvariable=self._manual_var,
            justify="center",
            width=6,
            font=("DejaVu Sans", FS_TITLE, "bold"),
            bg=COL_CARD,
            fg=COL_TEXT,
            highlightbackground=COL_BORDER,
            highlightcolor=COL_ACCENT,
            highlightthickness=1,
            insertbackground=COL_TEXT,
        )
        entry.pack(pady=(6, 0))
        bind_numeric_entry(entry, decimals=0)

        tk.Button(
            custom_frame,
            text="Teclado",
            command=self._open_numeric_keyboard,
            bg=COL_ACCENT,
            fg=COL_TEXT,
            activebackground=COL_ACCENT,
            activeforeground=COL_TEXT,
            relief="flat",
            cursor="hand2",
            font=("DejaVu Sans", FS_TEXT - 2, "bold"),
            highlightthickness=0,
        ).pack(pady=(6, 0))

        hint = tk.Label(
            custom_frame,
            text="Máximo 120 minutos",
            bg=COL_CARD,
            fg=COL_MUTED,
            font=("DejaVu Sans", FS_TEXT - 2),
        )
        hint.pack(pady=(4, 0))

        buttons = tk.Frame(container, bg=COL_CARD)
        buttons.pack(pady=(12, 0), fill="x")

        self._start_btn = tk.Button(
            buttons,
            text="Aceptar",
            command=self._start_from_entry,
            bg=COL_ACCENT,
            fg=COL_TEXT,
            activebackground=COL_ACCENT,
            activeforeground=COL_TEXT,
            bd=0,
            relief="flat",
            font=("DejaVu Sans", FS_BTN_SMALL, "bold"),
            cursor="hand2",
            highlightthickness=0,
        )
        self._start_btn.pack(side="left", expand=True, fill="x", padx=(0, 8))

        self._cancel_btn = tk.Button(
            buttons,
            text="Cancelar",
            command=self._cancel_timer,
            bg=COL_DANGER,
            fg=COL_TEXT,
            activebackground=COL_DANGER,
            activeforeground=COL_TEXT,
            bd=0,
            relief="flat",
            font=("DejaVu Sans", FS_BTN_SMALL, "bold"),
            cursor="hand2",
            highlightthickness=0,
        )
        self._cancel_btn.pack(side="left", expand=True, fill="x")

        self.controller.notify_current()
        self.bind("<Destroy>", self._on_destroy)

    # ------------------------------------------------------------------
    def show(self) -> None:
        self._manual_var.set(str(self.controller.last_minutes))
        super().show()

    # ------------------------------------------------------------------
    def _start_from_preset(self, minutes: int) -> None:
        minutes = max(1, min(int(minutes), MAX_MINUTES))
        self._manual_var.set(str(minutes))
        self.controller.start(minutes * 60)
        self.hide()

    def _start_from_entry(self) -> None:
        raw = self._manual_var.get().strip()
        try:
            minutes = int(raw)
        except Exception:
            minutes = 0
        if minutes <= 0:
            self._status_var.set("Introduce un valor entre 1 y 120 minutos.")
            return
        if minutes > MAX_MINUTES:
            self._status_var.set("El máximo son 120 minutos.")
            return
        self.controller.start(minutes * 60)
        self.hide()

    def _open_numeric_keyboard(self) -> None:
        if NumericKeyPopup is None:
            return

        def _accept(value: str) -> None:
            clean = value.strip()
            if not clean:
                self._status_var.set("Introduce un valor entre 1 y 120 minutos.")
                return
            try:
                minutes = int(clean)
            except Exception:
                self._status_var.set("Introduce un número válido.")
                return
            minutes = max(1, min(minutes, MAX_MINUTES))
            if minutes != int(clean):
                self._status_var.set("El rango válido es 1-120 minutos.")
            else:
                self._status_var.set("")
            self._manual_var.set(str(minutes))

        NumericKeyPopup(
            self,
            title="Minutos",
            initial=self._manual_var.get(),
            on_accept=_accept,
            allow_negative=False,
            allow_decimal=False,
        )

    def _cancel_timer(self) -> None:
        self.controller.cancel()
        self.hide()

    def _handle_timer_update(self, seconds: Optional[int], state: str) -> None:
        if state == "running" and seconds is not None:
            message = f"Cuenta atrás: {_format_seconds(seconds)}"
            self._cancel_btn.configure(state="normal")
        elif state == "finished":
            message = "Temporizador finalizado"
            self._cancel_btn.configure(state="normal")
        else:
            message = "Sin temporizador activo"
            self._cancel_btn.configure(state="disabled")
        self._status_var.set(message)

    def _on_destroy(self, _event: tk.Event) -> None:
        if self._listener:
            self.controller.remove_listener(self._listener)
            self._listener = None


__all__ = ["TimerController", "TimerOverlay", "_format_seconds"]

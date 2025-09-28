"""Timer dialog and countdown controller for the holographic UI."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import time
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from .. import theme_holo
from ..widgets_keypad import NeoKeypad

__all__ = ["TimerState", "TimerController", "TimerDialog", "parse_digits"]


MAX_SECONDS = 99 * 60 + 59


class TimerState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class TimerEvent:
    state: TimerState
    remaining: Optional[int]
    flash: bool = False


def parse_digits(digits: str) -> int:
    """Translate a ``mmss`` string into a valid seconds payload."""

    cleaned = "".join(filter(str.isdigit, digits))
    if not cleaned:
        return 0
    trimmed = cleaned[-4:]
    padded = trimmed.rjust(4, "0")
    minutes = int(padded[:-2])
    seconds = int(padded[-2:])

    if seconds >= 60:
        minutes += seconds // 60
        seconds = seconds % 60

    if minutes > 99:
        minutes = 99
        seconds = 59

    total = minutes * 60 + seconds
    return min(total, MAX_SECONDS)


class TimerController:
    """Robust countdown manager orchestrating toolbar updates."""

    def __init__(
        self,
        root: tk.Misc,
        *,
        on_finish: Optional[Callable[[], None]] = None,
    ) -> None:
        self._root = root
        self._on_finish = on_finish
        self._listeners: list[Callable[[TimerEvent], None]] = []
        self._state = TimerState.IDLE
        self._deadline: float | None = None
        self._remaining_snapshot = 0
        self._tick_job: str | None = None
        self._flash_job: str | None = None
        self._flash_deadline: float | None = None
        self._flash_visible = False
        self._last_reported: Optional[int] = None
        self._last_programmed = 60

    # ------------------------------------------------------------------
    def add_listener(self, callback: Callable[[TimerEvent], None], *, fire: bool = True) -> None:
        if callback in self._listeners:
            return
        self._listeners.append(callback)
        if fire:
            try:
                callback(
                    TimerEvent(
                        self._state,
                        self.get_remaining() if self._state != TimerState.IDLE else None,
                    )
                )
            except Exception:
                pass

    def remove_listener(self, callback: Callable[[TimerEvent], None]) -> None:
        try:
            self._listeners.remove(callback)
        except ValueError:
            pass

    # ------------------------------------------------------------------
    def open_dialog_initial(self) -> int:
        return max(1, min(self._last_programmed, MAX_SECONDS))

    def get_remaining(self) -> int:
        if self._state == TimerState.RUNNING and self._deadline is not None:
            remaining = int(max(0, round(self._deadline - time.monotonic())))
            return remaining
        if self._state == TimerState.PAUSED:
            return int(max(0, self._remaining_snapshot))
        return 0

    def start(self, total_seconds: int) -> None:
        seconds = max(1, min(int(total_seconds), MAX_SECONDS))
        self._last_programmed = seconds
        self._cancel_jobs()
        self._state = TimerState.RUNNING
        self._deadline = time.monotonic() + seconds
        self._remaining_snapshot = seconds
        self._last_reported = None
        self._notify(self._state, seconds)
        self._schedule_tick()

    def pause(self) -> None:
        if self._state != TimerState.RUNNING:
            return
        remaining = self.get_remaining()
        self._cancel_tick()
        self._state = TimerState.PAUSED
        self._deadline = None
        self._remaining_snapshot = remaining
        self._notify(self._state, remaining)

    def resume(self) -> None:
        if self._state != TimerState.PAUSED:
            return
        remaining = int(self._remaining_snapshot)
        if remaining <= 0:
            self._finish()
            return
        self._state = TimerState.RUNNING
        self._deadline = time.monotonic() + remaining
        self._last_reported = None
        self._notify(self._state, remaining)
        self._schedule_tick()

    def cancel(self) -> None:
        if self._state == TimerState.IDLE:
            return
        self._cancel_jobs()
        self._state = TimerState.CANCELLED
        self._deadline = None
        self._remaining_snapshot = 0
        self._notify(self._state, None)
        self._state = TimerState.IDLE
        self._notify(self._state, None)

    # ------------------------------------------------------------------
    def _schedule_tick(self) -> None:
        self._cancel_tick()
        self._tick_job = self._root.after(250, self._tick)

    def _cancel_tick(self) -> None:
        if self._tick_job is None:
            return
        try:
            self._root.after_cancel(self._tick_job)
        except Exception:
            pass
        self._tick_job = None

    def _cancel_flash(self) -> None:
        if self._flash_job is None:
            return
        try:
            self._root.after_cancel(self._flash_job)
        except Exception:
            pass
        self._flash_job = None

    def _cancel_jobs(self) -> None:
        self._cancel_tick()
        self._cancel_flash()
        self._flash_deadline = None
        self._flash_visible = False

    def _tick(self) -> None:
        self._tick_job = None
        if self._state != TimerState.RUNNING or self._deadline is None:
            return
        remaining = self.get_remaining()
        if remaining <= 0:
            self._finish()
            return
        if remaining != self._last_reported:
            self._last_reported = remaining
            self._notify(TimerState.RUNNING, remaining)
        self._schedule_tick()

    def _finish(self) -> None:
        self._cancel_tick()
        self._state = TimerState.FINISHED
        self._deadline = None
        self._remaining_snapshot = 0
        self._flash_deadline = time.monotonic() + 10.0
        self._flash_visible = True
        self._notify(self._state, 0, flash=True)
        if self._on_finish:
            try:
                self._on_finish()
            except Exception:
                pass
        self._schedule_flash()

    def _schedule_flash(self) -> None:
        self._cancel_flash()
        self._flash_job = self._root.after(500, self._flash_tick)

    def _flash_tick(self) -> None:
        self._flash_job = None
        if self._state != TimerState.FINISHED:
            return
        now = time.monotonic()
        if self._flash_deadline is not None and now >= self._flash_deadline:
            self._flash_deadline = None
            self._state = TimerState.IDLE
            self._notify(self._state, None)
            return
        self._flash_visible = not self._flash_visible
        self._notify(TimerState.FINISHED, 0, flash=self._flash_visible)
        self._schedule_flash()

    def _notify(self, state: TimerState, remaining: Optional[int], *, flash: bool = False) -> None:
        event = TimerEvent(state=state, remaining=remaining, flash=flash)
        for callback in list(self._listeners):
            try:
                callback(event)
            except Exception:
                continue


class TimerDialog(tk.Toplevel):
    """Non-blocking dialog used to configure the shared timer."""

    PRESETS = (30, 60, 120, 300, 600)

    def __init__(
        self,
        parent: tk.Misc,
        controller: object,
        *,
        width: int = 720,
        height: int = 520,
    ) -> None:
        super().__init__(parent)
        self.withdraw()
        self.title("Temporizador")
        self.overrideredirect(False)
        self.resizable(False, False)
        self.configure(bg=theme_holo.COLOR_BG)

        self._parent = parent
        self._controller = controller
        self._width = width
        self._height = height
        self._digits = ""
        self._last_applied_seconds = 0
        self._keypad: Optional[NeoKeypad] = None

        self._display_var = tk.StringVar(value=theme_holo.format_mmss(0))
        self._status_var = tk.StringVar(value="")

        theme_holo.apply_holo_theme(self)
        self._build_ui()

        self.bind("<Escape>", lambda _e: self.close())
        self.bind("<Return>", lambda _e: self._accept())
        self.bind("<KeyPress>", self._handle_keypress, add=True)

        self.protocol("WM_DELETE_WINDOW", self.close)

    # ------------------------------------------------------------------
    def show(self, *, initial_seconds: Optional[int] = None) -> None:
        self._reset_view(initial_seconds)
        self._center_on_parent()
        self.deiconify()
        self.lift()
        try:
            self.grab_set()
        except Exception:
            pass
        self.after_idle(self._focus_keypad)

    def close(self) -> None:
        try:
            self.grab_release()
        except Exception:
            pass
        self.withdraw()

    # ------------------------------------------------------------------
    def update_from_event(self, event: TimerEvent) -> None:
        if event.state == TimerState.RUNNING and event.remaining is not None:
            self._status_var.set("Temporizador en marcha")
        elif event.state == TimerState.PAUSED and event.remaining is not None:
            self._status_var.set("Temporizador en pausa")
        elif event.state == TimerState.FINISHED:
            self._status_var.set("Temporizador finalizado")
        elif event.state == TimerState.CANCELLED:
            self._status_var.set("Temporizador cancelado")
        else:
            self._status_var.set("")

        if event.state in {TimerState.RUNNING, TimerState.PAUSED} and event.remaining is not None:
            self._display_var.set(theme_holo.format_mmss(event.remaining))
        elif self._digits:
            seconds = parse_digits(self._digits)
            self._display_var.set(theme_holo.format_mmss(seconds))
        elif event.remaining is None:
            self._display_var.set(theme_holo.format_mmss(0))

    def set_last_programmed(self, seconds: int) -> None:
        self._last_applied_seconds = max(0, int(seconds))

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        container = ttk.Frame(self, padding=24, style="Timer.Dialog.TFrame")
        container.pack(fill="both", expand=True)
        style = theme_holo.get_style(self)
        style.configure("Timer.Dialog.TFrame", background=theme_holo.COLOR_BG)

        header = ttk.Label(
            container,
            text="Temporizador",
            style="Timer.Title.TLabel",
            anchor="center",
        )
        header.pack(pady=(0, 16))
        style.configure(
            "Timer.Title.TLabel",
            background=theme_holo.COLOR_BG,
            foreground=theme_holo.COLOR_PRIMARY,
            font=theme_holo.FONT_HEADER,
        )

        display = ttk.Label(
            container,
            textvariable=self._display_var,
            style="Timer.Display.TLabel",
            anchor="center",
        )
        display.pack(fill="x", pady=(0, 16))
        style.configure(
            "Timer.Display.TLabel",
            background=theme_holo.COLOR_BG,
            foreground=theme_holo.COLOR_ACCENT,
            font=theme_holo.FONT_DIGITS,
        )

        status = ttk.Label(
            container,
            textvariable=self._status_var,
            style="Timer.Status.TLabel",
            anchor="center",
        )
        status.pack(fill="x", pady=(0, 12))
        style.configure(
            "Timer.Status.TLabel",
            background=theme_holo.COLOR_BG,
            foreground=theme_holo.COLOR_TEXT_MUTED,
            font=theme_holo.FONT_BODY,
        )

        layout = ttk.Frame(container, style="Timer.Dialog.TFrame")
        layout.pack(fill="both", expand=True)

        presets = ttk.Frame(layout, style="Timer.Presets.TFrame")
        presets.pack(side="left", fill="y", padx=(0, 24))
        style.configure("Timer.Presets.TFrame", background=theme_holo.COLOR_BG)

        for value in self.PRESETS:
            button = theme_holo.create_neon_button(
                presets,
                text=theme_holo.format_mmss(value),
                command=lambda v=value: self._apply_preset(v),
                width=10,
            )
            button.pack(fill="x", pady=6)

        keypad = NeoKeypad(
            layout,
            on_digit=self._handle_digit,
            on_backspace=self._handle_backspace,
            on_clear=self._clear_digits,
            on_accept=self._accept,
            on_cancel=self.close,
        )
        keypad.pack(side="right", fill="both", expand=True)
        self._keypad = keypad

    # ------------------------------------------------------------------
    def _reset_view(self, initial_seconds: Optional[int]) -> None:
        seconds = initial_seconds if initial_seconds is not None else self._last_applied_seconds
        seconds = max(0, min(int(seconds), MAX_SECONDS))
        self._digits = f"{seconds // 60:02d}{seconds % 60:02d}" if seconds else ""
        self._display_var.set(theme_holo.format_mmss(seconds))
        self._status_var.set("")
        self._last_applied_seconds = seconds or self._last_applied_seconds

    def _focus_keypad(self) -> None:
        try:
            self._keypad.focus_keypad()
        except Exception:
            pass

    def _apply_preset(self, seconds: int) -> None:
        seconds = max(1, min(int(seconds), MAX_SECONDS))
        self._digits = f"{seconds // 60:02d}{seconds % 60:02d}"
        self._display_var.set(theme_holo.format_mmss(seconds))
        self._status_var.set("")
        self._last_applied_seconds = seconds

    def _handle_digit(self, value: str) -> None:
        self._digits = (self._digits + value)[-4:]
        seconds = parse_digits(self._digits)
        self._display_var.set(theme_holo.format_mmss(seconds))
        self._status_var.set("")

    def _handle_backspace(self) -> None:
        self._digits = self._digits[:-1]
        seconds = parse_digits(self._digits)
        self._display_var.set(theme_holo.format_mmss(seconds))

    def _clear_digits(self) -> None:
        self._digits = ""
        self._display_var.set(theme_holo.format_mmss(0))

    def _accept(self) -> None:
        seconds = parse_digits(self._digits)
        if seconds <= 0:
            self._status_var.set("Introduce un tiempo válido (00:01 – 99:59)")
            return
        self._last_applied_seconds = seconds
        start = getattr(self._controller, "timer_start", None)
        if callable(start):
            try:
                start(seconds)
            except Exception:
                pass
        self.close()

    def _handle_keypress(self, event: tk.Event) -> None:
        if event.keysym == "BackSpace":
            self._handle_backspace()
        elif event.char and event.char.isdigit():
            self._handle_digit(event.char)

    def _center_on_parent(self) -> None:
        parent = self._parent.winfo_toplevel() if hasattr(self._parent, "winfo_toplevel") else self._parent
        try:
            parent.update_idletasks()
        except Exception:
            pass

        try:
            pw = int(parent.winfo_width())
            ph = int(parent.winfo_height())
            px = int(parent.winfo_rootx())
            py = int(parent.winfo_rooty())
        except Exception:
            pw = 1024
            ph = 600
            px = 0
            py = 0

        w = min(self._width, pw)
        h = min(self._height, ph)
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        screen_w = max(800, int(self.winfo_screenwidth()))
        screen_h = max(480, int(self.winfo_screenheight()))
        x = max(0, min(x, screen_w - w))
        y = max(0, min(y, screen_h - h))
        self.geometry(f"{w}x{h}+{x}+{y}")

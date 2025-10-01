"""Timer dialog and countdown controller for the holographic UI."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

import tkinter as tk
from tkinter import ttk

import os, sys, logging

AUDIT = os.environ.get("BASCULA_UI_AUDIT") == "1"
TAUD = logging.getLogger("ui.audit.timer")
if AUDIT:
    TAUD.setLevel(logging.DEBUG)
    if not TAUD.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(logging.Formatter("AUDIT %(message)s"))
        TAUD.addHandler(h)
    TAUD.propagate = False
    TAUD.debug(f"timer={__file__}")

from .. import theme_holo
from ..widgets_keypad import NeoKeypad
from bascula.services import sound

__all__ = [
    "TimerState",
    "TimerController",
    "TimerDialog",
    "TimerEvent",
    "parse_digits",
    "get_timer_controller",
]


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
        self._tick_counter = 0
        self._audit_i = 0

    # ------------------------------------------------------------------
    def set_on_finish(self, callback: Optional[Callable[[], None]]) -> None:
        self._on_finish = callback

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
        self._audit_i = 0
        self._state = TimerState.RUNNING
        if AUDIT:
            TAUD.debug(f"timer state change -> {self._state.name}")
        self._deadline = time.monotonic() + seconds
        self._remaining_snapshot = seconds
        self._last_reported = None
        self._tick_counter = 0
        self._notify(self._state, seconds)
        self._schedule_tick()

    def pause(self) -> None:
        if self._state != TimerState.RUNNING:
            return
        remaining = self.get_remaining()
        self._cancel_tick()
        self._state = TimerState.PAUSED
        if AUDIT:
            TAUD.debug(f"timer state change -> {self._state.name}")
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
        self._audit_i = 0
        self._state = TimerState.RUNNING
        if AUDIT:
            TAUD.debug(f"timer state change -> {self._state.name}")
        self._deadline = time.monotonic() + remaining
        self._last_reported = None
        self._tick_counter = 0
        self._notify(self._state, remaining)
        self._schedule_tick()

    def cancel(self) -> None:
        if self._state == TimerState.IDLE:
            return
        self._cancel_jobs()
        self._state = TimerState.CANCELLED
        if AUDIT:
            TAUD.debug(f"timer state change -> {self._state.name}")
        self._deadline = None
        self._remaining_snapshot = 0
        self._notify(self._state, None)
        self._state = TimerState.IDLE
        if AUDIT:
            TAUD.debug(f"timer state change -> {self._state.name}")
        self._notify(self._state, None)

    # ------------------------------------------------------------------
    def _schedule_tick(self) -> None:
        self._cancel_tick()
        self._tick_job = self._root.after(500, self._tick)

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
        self._tick_counter += 1
        remaining = self.get_remaining()
        if remaining <= 0:
            self._finish()
            return
        if AUDIT:
            idx = getattr(self, "_audit_i", 0)
            try:
                state_name = self._state.name
            except Exception:
                state_name = str(self._state)
            if idx % 5 == 0:
                TAUD.debug(f"timer tick state={state_name} remaining={remaining}")
            self._audit_i = idx + 1
        self._last_reported = remaining
        self._notify(TimerState.RUNNING, remaining)
        self._schedule_tick()

    def _finish(self) -> None:
        self._cancel_tick()
        self._state = TimerState.FINISHED
        if AUDIT:
            TAUD.debug(f"timer state change -> {self._state.name}")
        self._deadline = None
        self._remaining_snapshot = 0
        self._flash_deadline = time.monotonic() + 10.0
        self._flash_visible = True
        self._notify(self._state, 0, flash=True)
        self._trigger_completion_feedback()
        if self._on_finish:
            try:
                self._on_finish()
            except Exception:
                pass
        self._schedule_flash()

    def _trigger_completion_feedback(self) -> None:
        try:
            threading.Thread(target=sound.play_beep, daemon=True).start()
        except Exception:
            pass
        try:
            threading.Thread(
                target=lambda: sound.speak("Tiempo finalizado"),
                daemon=True,
            ).start()
        except Exception:
            pass

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
            if AUDIT:
                TAUD.debug(f"timer state change -> {self._state.name}")
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
        if AUDIT:
            TAUD.debug("TimerDialog __init__ enter")
        self.withdraw()
        before_flag = 0
        try:
            before_flag = int(bool(self.overrideredirect()))
        except Exception:
            before_flag = 0
        if AUDIT:
            TAUD.debug(f"before overrideredirect={before_flag}")
        try:
            self.overrideredirect(True)
        except Exception:
            pass
        after_flag = 0
        try:
            after_flag = int(bool(self.overrideredirect()))
        except Exception:
            after_flag = 0
        if AUDIT:
            TAUD.debug(f"after overrideredirect={after_flag}")
        try:
            master = parent.winfo_toplevel()
        except Exception:
            master = parent
        try:
            self.transient(master)
        except Exception:
            pass
        self.resizable(False, False)
        self.configure(bg=theme_holo.COLOR_BG)

        self._parent = parent
        self._controller = controller
        self._width = width
        self._height = height
        self._digits = ""
        self._last_applied_seconds = 0
        self._keypad: Optional[NeoKeypad] = None
        self._suppress_show = True

        self._display_var = tk.StringVar(value=theme_holo.format_mmss(0))
        self._status_var = tk.StringVar(value="")

        theme_holo.apply_holo_theme(self)
        self._build_ui()

        self.bind("<Escape>", lambda _e: self.close())
        self.bind("<Return>", lambda _e: self._accept())
        self.bind("<KeyPress>", self._handle_keypress, add=True)

        self.protocol("WM_DELETE_WINDOW", self.close)

        self._suppress_show = False
        try:
            self.update_idletasks()
        except Exception:
            pass
        topmost_applied = False
        try:
            self.attributes("-topmost", True)
            topmost_applied = True
        except Exception:
            topmost_applied = False

        self._center_and_show()

        try:
            self.lift()
        except Exception:
            pass

        if topmost_applied:
            def _drop_topmost() -> None:
                try:
                    self.attributes("-topmost", False)
                except Exception:
                    pass

            self.after_idle(_drop_topmost)

        if AUDIT:
            try:
                topmost = (
                    self.attributes("-topmost") if hasattr(self, "attributes") else "n/a"
                )
            except Exception as exc:
                topmost = f"error: {exc}"
            TAUD.debug(f"shown geometry={self.geometry()} topmost={topmost}")

    # ------------------------------------------------------------------
    def show(self, *, initial_seconds: Optional[int] = None) -> None:
        self._reset_view(initial_seconds)
        self._center_and_show(self._width, self._height)
        self.lift()
        self.after_idle(self._focus_keypad)

    def close(self) -> None:
        if AUDIT:
            TAUD.debug("TimerDialog close() called (withdraw)")
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

    def _center_and_show(self, width: Optional[int] = None, height: Optional[int] = None) -> None:
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        if width is None:
            width = max(640, int(self.winfo_reqwidth()))
        if height is None:
            height = max(400, int(self.winfo_reqheight()))
        x = max(0, (sw - width) // 2)
        y = max(0, (sh - height) // 2)
        try:
            self.configure(bg=theme_holo.COLOR_BG)
        except Exception:
            pass
        self.geometry(f"{width}x{height}+{x}+{y}")
        if self._suppress_show:
            return
        try:
            self.grab_set()
        except Exception:
            pass
        try:
            self.focus_set()
        except Exception:
            pass
        self.deiconify()


_controller_singleton: Optional[TimerController] = None


def get_timer_controller(
    root: tk.Misc, *, on_finish: Optional[Callable[[], None]] = None
) -> TimerController:
    """Return a shared ``TimerController`` instance bound to ``root``."""

    global _controller_singleton
    if _controller_singleton is None:
        _controller_singleton = TimerController(root=root, on_finish=on_finish)
        return _controller_singleton

    if on_finish is not None:
        try:
            _controller_singleton.set_on_finish(on_finish)
        except Exception:
            pass
    return _controller_singleton

"""Animated mascot canvas used throughout the UI."""

from __future__ import annotations

import random
import tkinter as tk
from typing import Callable, Optional

from bascula.config.theme import get_current_colors

_COLORS = get_current_colors()
COL_ACCENT = _COLORS["COL_ACCENT"]
COL_BG = _COLORS["COL_BG"]
COL_CARD = _COLORS["COL_CARD"]
COL_BORDER = _COLORS["COL_BORDER"]
COL_TEXT = _COLORS["COL_TEXT"]


def refresh_palette() -> None:
    """Update global colours when the theme changes."""

    global _COLORS, COL_ACCENT, COL_BG, COL_CARD, COL_BORDER, COL_TEXT
    _COLORS = get_current_colors()
    COL_ACCENT = _COLORS["COL_ACCENT"]
    COL_BG = _COLORS["COL_BG"]
    COL_CARD = _COLORS["COL_CARD"]
    COL_BORDER = _COLORS["COL_BORDER"]
    COL_TEXT = _COLORS["COL_TEXT"]


class MascotaCanvas(tk.Canvas):
    """Friendly mascot with small idle animations and reactions.

    The original kiosk included a lively assistant that reacted to taps,
    confirmations and warnings.  Several modules – focus mode, overlays and
    toast notifications – still call ``set_state`` or ``react`` even though the
    stripped down canvas no longer implemented those hooks.  This class restores
    the behaviour in a compact yet fully themed way.
    """

    _STATES = {
        "idle": (COL_ACCENT, COL_BG),
        "listen": ("#34d399", COL_BG),
        "process": ("#10b981", COL_BG),
        "happy": ("#22d3ee", COL_BG),
        "error": ("#f87171", COL_BG),
    }

    def __init__(self, master: tk.Misc, width: int = 220, height: int = 220, **kwargs) -> None:
        super().__init__(master, width=width, height=height, highlightthickness=0, **kwargs)
        self.configure(bg=COL_CARD)

        self._state = "idle"
        self._blink_job: Optional[str] = None
        self._idle_job: Optional[str] = None
        self._pulse_job: Optional[str] = None
        self._frame = 0
        self._tap_cb: Optional[Callable[[], None]] = None
        self._running = False
        self._idle_cycle = [0, 1, 2, 1, 0, -1, -2, -1]
        self._idle_offset = 0

        self.bind("<Button-1>", self._on_tap)
        self._draw_mascot()

    # ------------------------------------------------------------------ drawing
    def _draw_mascot(self, blink: bool = False) -> None:
        self.delete("all")
        base_color, face_bg = self._STATES.get(self._state, (COL_ACCENT, COL_BG))

        body_outline = COL_BORDER
        eye_color = COL_BG if not blink else base_color
        mouth_color = COL_BG if self._state != "error" else "#1f2937"

        # Body
        self.create_oval(26, 70, 194, 218, fill=base_color, outline=body_outline, width=4)
        # Head
        self.create_oval(42, 16, 178, 148, fill=base_color, outline=body_outline, width=4)

        # Eyes
        self.create_oval(82, 70, 110, 98, fill=eye_color, outline=body_outline, width=2)
        self.create_oval(134, 70, 162, 98, fill=eye_color, outline=body_outline, width=2)
        if blink:
            self.create_line(84, 84, 108, 84, fill=body_outline, width=3)
            self.create_line(136, 84, 160, 84, fill=body_outline, width=3)

        # Mouth / screen
        if self._state == "happy":
            self.create_arc(88, 96, 156, 142, start=190, extent=160, style="arc", outline=COL_TEXT, width=4)
        elif self._state == "error":
            self.create_line(94, 116, 150, 116, fill=COL_TEXT, width=4)
        else:
            self.create_rectangle(94, 104, 150, 130, fill=mouth_color, outline=body_outline, width=2)

        # Feet
        self.create_rectangle(74, 210, 110, 240, fill=base_color, outline=body_outline, width=4)
        self.create_rectangle(130, 210, 166, 240, fill=base_color, outline=body_outline, width=4)

    # ------------------------------------------------------------------ states
    def set_state(self, state: str) -> None:
        state = state or "idle"
        if state not in self._STATES:
            state = "idle"
        self._state = state
        self._draw_mascot()
        if self._running:
            self._schedule_blink(reset=True)

    def on_tap(self, callback: Callable[[], None]) -> None:
        """Register a callback executed when the mascot is tapped."""

        self._tap_cb = callback

    def react(self, event: str) -> None:
        event = (event or "").lower()
        if event in {"tap", "poke"}:
            self._pulse()
        elif event in {"success", "ok"}:
            self._flash("happy")
        elif event in {"error", "warn", "warning"}:
            self._flash("error")
        else:
            self._flash("idle")

    # Convenience aliases used by mascot_messages animations
    def bounce(self) -> None:
        self._pulse()

    def wink(self) -> None:
        self._draw_mascot(blink=True)
        self.after(220, self._draw_mascot)

    def shake(self) -> None:
        offsets = [(-6, 0), (6, 0), (-3, 0), (3, 0), (0, 0)]

        def _step(idx: int = 0, prev: tuple[int, int] = (0, 0)) -> None:
            if idx >= len(offsets):
                self.move("all", -prev[0], -prev[1])
                self._draw_mascot()
                return
            dx, dy = offsets[idx]
            self.move("all", dx - prev[0], dy - prev[1])
            self.after(60, lambda: _step(idx + 1, (dx, dy)))

        _step()

    def happy(self) -> None:
        self._flash("happy")

    def error(self) -> None:
        self._flash("error")

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._draw_mascot()
        self._schedule_blink(reset=True)
        self._start_idle()

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        for job in (self._blink_job, self._idle_job, self._pulse_job):
            if job:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
        self._blink_job = self._idle_job = self._pulse_job = None
        if self._idle_offset:
            try:
                self.move("all", 0, -self._idle_offset)
            except Exception:
                pass
            self._idle_offset = 0
        self._draw_mascot()

    # ------------------------------------------------------------------ animations
    def _schedule_blink(self, reset: bool = False) -> None:
        if self._blink_job and reset:
            try:
                self.after_cancel(self._blink_job)
            except Exception:
                pass
            self._blink_job = None

        if self._blink_job is not None:
            return

        if not self._running:
            return

        delay = random.randint(3000, 6000)

        def _blink_once() -> None:
            self._draw_mascot(blink=True)
            self.after(160, self._draw_mascot)
            self._blink_job = None
            self._schedule_blink()

        self._blink_job = self.after(delay, _blink_once)

    def _start_idle(self) -> None:
        if self._idle_job:
            try:
                self.after_cancel(self._idle_job)
            except Exception:
                pass
            self._idle_job = None

        if not self._running:
            return

        cycle = list(self._idle_cycle)
        self._idle_offset = 0

        def _step(index: int = 0, previous: int = 0) -> None:
            if not self._running:
                return
            try:
                offset = cycle[index % len(cycle)]
            except Exception:
                offset = 0
            try:
                self.move("all", 0, offset - previous)
            except Exception:
                pass
            self._idle_offset += offset - previous
            delay = random.randint(80, 120)
            self._idle_job = self.after(delay, lambda: _step((index + 1) % len(cycle), offset))

        self._idle_job = self.after(random.randint(80, 120), _step)

    def _pulse(self) -> None:
        if self._pulse_job:
            try:
                self.after_cancel(self._pulse_job)
            except Exception:
                pass
            self._pulse_job = None

        scale = {0: 1.0, 1: 1.06, 2: 1.0, 3: 0.92, 4: 1.0}

        def _tick(step: int = 0) -> None:
            if step >= len(scale):
                self.scale("all", 0, 0, 1.0, 1.0)
                self._draw_mascot()
                return
            factor = scale[step]
            self.scale("all", 110, 130, factor, factor)
            self.after(80, lambda: _tick(step + 1))

        self._pulse_job = self.after(0, _tick)

    def _flash(self, temp_state: str, duration: int = 900) -> None:
        current = self._state

        def _apply() -> None:
            self._state = temp_state
            self._draw_mascot()

        def _restore() -> None:
            self._state = current
            self._draw_mascot()
            if self._running:
                self._schedule_blink(reset=True)

        _apply()
        self.after(duration, _restore)

    # ------------------------------------------------------------------ events
    def _on_tap(self, _event) -> None:
        self.react("tap")
        if callable(self._tap_cb):
            try:
                self._tap_cb()
            except Exception:
                pass

    def refresh(self) -> None:
        """Redraw the mascot immediately."""

        self._draw_mascot()


__all__ = ["MascotaCanvas", "refresh_palette"]

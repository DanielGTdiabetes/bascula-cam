from __future__ import annotations

"""
Typewriter-like text label for Tkinter with optional effect.

Usage:
    lbl = TypewriterLabel(parent, text="Hola mundo", enabled=True)
    lbl.pack()

    # Later: update text
    lbl.set_text("Nuevo texto")
    # Disable effect on demand
    lbl.set_enabled(False)

Notes:
    - When enabled=False, behaves like a normal Label (no animation, no sound).
    - Sound uses tk.bell() by default (very short click). It can be disabled or
      replaced with a custom callable via sound_fn.
"""

import tkinter as tk
from typing import Optional, Callable, Iterable


class TypewriterLabel(tk.Label):
    def __init__(
        self,
        parent,
        text: str = "",
        enabled: bool = True,
        speed_ms: int = 45,
        cursor: str = "_",
        blink_ms: int = 500,
        sound_mode: str = "off",  # 'off' | 'tk' | 'custom'
        sound_every: str = "char",  # 'char' | 'word'
        word_pause_ms: int = 60,
        charset_pause: Optional[Iterable[str]] = None,
        sound_fn: Optional[Callable[[], None]] = None,
        **kwargs,
    ) -> None:
        super().__init__(parent, **kwargs)

        self._full_text: str = str(text or "")
        self._shown: str = ""
        self._i: int = 0
        self._enabled: bool = bool(enabled)

        self._speed_ms: int = max(1, int(speed_ms))
        self._cursor_char: str = str(cursor or "")
        self._blink_ms: int = max(120, int(blink_ms))
        self._cursor_on: bool = True

        self._word_pause_ms: int = max(0, int(word_pause_ms))
        self._charset_pause = set(charset_pause) if charset_pause else set(",.;:!? ")

        self._sound_mode: str = str(sound_mode or "off").lower()
        self._sound_every: str = str(sound_every or "char").lower()
        self._sound_fn: Optional[Callable[[], None]] = sound_fn

        self._typing_after: Optional[str] = None
        self._blink_after: Optional[str] = None

        # Initial paint
        if self._enabled:
            self._begin_typing()
        else:
            super().configure(text=self._full_text)

    # ---- Public API ----
    def set_text(self, text: str) -> None:
        self._cancel_timers()
        self._full_text = str(text or "")
        self._shown = ""
        self._i = 0
        if self._enabled:
            self._cursor_on = True
            self._begin_typing()
        else:
            super().configure(text=self._full_text)

    def set_enabled(self, value: bool) -> None:
        val = bool(value)
        if val == self._enabled:
            return
        self._enabled = val
        self.set_text(self._full_text)

    def configure(self, cnf=None, **kw):  # keep tk.Label API
        # Allow updating text via .configure(text=...)
        if kw and "text" in kw:
            self.set_text(kw.pop("text"))
        return super().configure(cnf, **kw)

    config = configure  # alias

    # ---- Internals ----
    def _begin_typing(self) -> None:
        self._schedule_blink()
        self._step_type()

    def _schedule_blink(self) -> None:
        if self._blink_after:
            try:
                self.after_cancel(self._blink_after)
            except Exception:
                pass
            self._blink_after = None
        # Only blink when enabled (typing or after typing)
        def _blink():
            self._cursor_on = not self._cursor_on
            self._update_label()
            self._blink_after = self.after(self._blink_ms, _blink)
        self._blink_after = self.after(self._blink_ms, _blink)

    def _step_type(self) -> None:
        # Done?
        if self._i >= len(self._full_text):
            self._update_label(final=True)
            return
        ch = self._full_text[self._i]
        self._shown += ch
        self._i += 1
        self._update_label()

        # Play sound if configured
        try:
            if self._sound_mode != "off":
                play = False
                if self._sound_every == "char":
                    play = True
                elif self._sound_every == "word" and ch in (" ", "\n", "\t"):
                    play = True
                if play:
                    self._do_sound()
        except Exception:
            pass

        # Next delay
        delay = self._speed_ms
        if ch in self._charset_pause:
            delay += self._word_pause_ms
        self._typing_after = self.after(delay, self._step_type)

    def _update_label(self, final: bool = False) -> None:
        if not self._enabled:
            super().configure(text=self._full_text)
            return
        txt = self._shown
        # Show cursor while typing, and after typing keep it blinking for effect
        if self._cursor_char and (not final or self._cursor_on):
            txt = f"{txt}{self._cursor_char if self._cursor_on else ' '}"
        super().configure(text=txt)

    def _do_sound(self) -> None:
        if self._sound_mode == "tk":
            try:
                self.bell()  # simple click
            except Exception:
                pass
        elif self._sound_mode == "custom" and callable(self._sound_fn):
            try:
                self._sound_fn()
            except Exception:
                pass

    def _cancel_timers(self) -> None:
        if self._typing_after:
            try:
                self.after_cancel(self._typing_after)
            except Exception:
                pass
            self._typing_after = None
        if self._blink_after:
            try:
                self.after_cancel(self._blink_after)
            except Exception:
                pass
            self._blink_after = None

    def destroy(self) -> None:
        self._cancel_timers()
        try:
            super().destroy()
        except Exception:
            pass


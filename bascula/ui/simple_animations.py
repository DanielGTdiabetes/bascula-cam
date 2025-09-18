"""Minimal animation helpers limited to two concurrent animations."""
from __future__ import annotations

import logging
import time
import tkinter as tk
from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque, Optional

logger = logging.getLogger("bascula.ui.simple_animations")


@dataclass(slots=True)
class Animation:
    widget: tk.Widget
    duration: int
    steps: int
    updater: Callable[[float], None]
    on_complete: Optional[Callable[[], None]] = None
    start_ts: float = 0.0


class AnimationManager:
    """Keeps the amount of concurrent animations under control."""

    def __init__(self, root: tk.Misc, *, max_parallel: int = 2) -> None:
        self.root = root
        self.max_parallel = max(1, max_parallel)
        self._active: list[Animation] = []
        self._queue: Deque[Animation] = deque()
        self._job: Optional[str] = None

    def schedule(
        self,
        widget: tk.Widget,
        *,
        duration: int = 240,
        steps: int = 4,
        updater: Callable[[float], None],
        on_complete: Optional[Callable[[], None]] = None,
    ) -> None:
        anim = Animation(widget=widget, duration=duration, steps=max(1, steps), updater=updater, on_complete=on_complete)
        anim.start_ts = time.monotonic()
        if len(self._active) < self.max_parallel:
            self._active.append(anim)
            self._ensure_loop()
        else:
            self._queue.append(anim)

    def _ensure_loop(self) -> None:
        if self._job is None:
            try:
                self._job = self.root.after(16, self._tick)
            except Exception:
                self._job = None

    def _tick(self) -> None:
        now = time.monotonic()
        next_active: list[Animation] = []
        for anim in list(self._active):
            elapsed = now - anim.start_ts
            progress = min(1.0, elapsed / (anim.duration / 1000.0))
            try:
                anim.updater(progress)
            except Exception:
                logger.debug("Animation updater failed", exc_info=True)
            if progress >= 1.0:
                if anim.on_complete:
                    try:
                        anim.on_complete()
                    except Exception:
                        logger.debug("Animation completion failed", exc_info=True)
                continue
            next_active.append(anim)
        self._active = next_active
        while len(self._active) < self.max_parallel and self._queue:
            anim = self._queue.popleft()
            anim.start_ts = now
            self._active.append(anim)
        if self._active:
            try:
                self._job = self.root.after(32, self._tick)
            except Exception:
                self._job = None
        else:
            self._job = None

    def cancel_all(self) -> None:
        self._queue.clear()
        self._active.clear()
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except Exception:
                pass
            self._job = None


def fade_between(widget: tk.Widget, *, manager: AnimationManager, start: float, end: float, duration: int = 200) -> None:
    def _update(progress: float) -> None:
        value = start + (end - start) * progress
        try:
            widget.configure(alpha=value)
        except Exception:
            # Tkinter does not support alpha by default; we use widget.after for compatibility.
            try:
                widget.tk.call("wm", "attributes", widget._w, "-alpha", value)  # type: ignore[attr-defined]
            except Exception:
                pass

    manager.schedule(widget, duration=duration, steps=4, updater=_update)


def pulse(widget: tk.Widget, *, manager: AnimationManager, scale: float = 1.02) -> None:
    base_width = max(1, widget.winfo_width())
    base_height = max(1, widget.winfo_height())

    def _update(progress: float) -> None:
        factor = 1.0 + (scale - 1.0) * (1.0 - abs(0.5 - progress)) * 2
        try:
            widget.scale("all", 0, 0, factor, factor)  # type: ignore[attr-defined]
        except Exception:
            # fallback: adjust padding
            pad = int(4 * (factor - 1.0))
            try:
                widget.configure(padx=pad, pady=pad)
            except Exception:
                pass

    manager.schedule(widget, duration=280, steps=5, updater=_update)


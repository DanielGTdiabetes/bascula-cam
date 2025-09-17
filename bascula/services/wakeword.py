from __future__ import annotations
"""Wake word engine interface and Porcupine stub.

Usage:
  engine = PorcupineWakeWord(keyword="basculin")
  engine.start()
  if engine.is_triggered():
      manejar_evento()
"""
import os
import random
import threading
import time
from typing import Callable, Optional, Protocol


class WakeWordEngine(Protocol):
    def start(self) -> None:
        """Start processing audio input."""
        raise NotImplementedError
    def stop(self) -> None:
        """Stop processing audio input."""
        raise NotImplementedError
    def is_triggered(self) -> bool:
        """Return True when the wake word has been detected."""
        raise NotImplementedError


class PorcupineWakeWord:
    """Stub implementation compatible with the expected interface.

    This does NOT bundle Porcupine; it provides a minimal structure so the
    application can toggle and poll without blocking the UI. Replace internal
    logic with real Porcupine integration where available.
    """

    def __init__(self, keyword: str = "basculin") -> None:
        self.keyword = (keyword or "").strip().lower()
        self._thr: Optional[threading.Thread] = None
        self._run = False
        self._flag = False

    def start(self) -> None:
        if self._thr and self._thr.is_alive():
            return
        self._run = True

        def _worker():
            # Placeholder loop; replace with real wake word processing
            while self._run:
                # Reset flag periodically; a real engine would set it on detection
                # Here we do nothing to avoid false triggers
                time.sleep(0.1)
        self._thr = threading.Thread(target=_worker, daemon=True)
        self._thr.start()

    def stop(self) -> None:
        self._run = False
        try:
            if self._thr and self._thr.is_alive():
                self._thr.join(timeout=0.1)
        except Exception:
            pass
        self._thr = None

    def is_triggered(self) -> bool:
        # A real engine would return True if the keyword was just detected.
        # Keep false by default to avoid spurious behavior.
        # External integrations can set _flag True when appropriate.
        f = self._flag
        self._flag = False
        return f

    # Optional method to simulate trigger in testing/development
    def _simulate_trigger(self) -> None:
        self._flag = True


class WakewordService:
    """High level wake word orchestrator with optional simulation."""

    def __init__(
        self,
        keyword: str = "basculin",
        *,
        on_detect: Optional[Callable[[], None]] = None,
        poll_interval: float = 0.12,
        simulate: Optional[bool] = None,
    ) -> None:
        self._engine: Optional[WakeWordEngine] = PorcupineWakeWord(keyword)
        self._thread: Optional[threading.Thread] = None
        self._active = False
        self._poll = max(0.05, float(poll_interval))
        env_sim = os.getenv("BASCULA_WAKEWORD_SIMULATE")
        if simulate is None:
            self._simulate = False if env_sim in {"0", "false", "False"} else True
        else:
            self._simulate = bool(simulate)
        self._on_detect = on_detect
        self._next_fake = 0.0

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        if self._active:
            return
        self._active = True
        if self._engine:
            try:
                self._engine.start()
            except Exception:
                pass
        self._schedule_fake_trigger()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._active = False
        if self._engine:
            try:
                self._engine.stop()
            except Exception:
                pass
        if self._thread and self._thread.is_alive():
            try:
                self._thread.join(timeout=0.2)
            except Exception:
                pass
        self._thread = None

    def is_active(self) -> bool:
        return self._active

    # ------------------------------------------------------------------ callbacks
    def set_on_detect(self, callback: Optional[Callable[[], None]]) -> None:
        self._on_detect = callback

    def trigger(self) -> None:
        """Manually notify detection (useful for tests)."""

        self._fire_callback()

    # ------------------------------------------------------------------ internals
    def _run_loop(self) -> None:
        while self._active:
            fired = False
            if self._engine:
                try:
                    if self._engine.is_triggered():
                        fired = True
                except Exception:
                    fired = False
            now = time.time()
            if fired:
                self._fire_callback()
                self._schedule_fake_trigger()
            elif self._simulate and now >= self._next_fake:
                self._fire_callback()
                self._schedule_fake_trigger()
            time.sleep(self._poll)

    def _schedule_fake_trigger(self) -> None:
        if not self._simulate:
            self._next_fake = float("inf")
            return
        base = random.uniform(18.0, 32.0)
        self._next_fake = time.time() + base

    def _fire_callback(self) -> None:
        cb = self._on_detect
        if callable(cb):
            try:
                cb()
            except Exception:
                pass


__all__ = ["PorcupineWakeWord", "WakewordService"]

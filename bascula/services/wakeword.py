from __future__ import annotations
"""Wake word engine interface and Porcupine stub.

Usage:
  engine = PorcupineWakeWord(keyword="basculin")
  engine.start()
  if engine.is_triggered(): ...
"""
import threading, time
from typing import Protocol, Optional


class WakeWordEngine(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def is_triggered(self) -> bool: ...


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

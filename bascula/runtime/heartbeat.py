"""Utilities for emitting heartbeat signals expected by safe_run."""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional

__all__ = ["HeartbeatWriter"]

log = logging.getLogger(__name__)


class HeartbeatWriter:
    """Periodically touch a file so watchdog scripts detect the UI is alive."""

    def __init__(self, file_path: str | os.PathLike[str] = "/run/bascula/heartbeat", interval: float = 2.0) -> None:
        self._file_path = Path(file_path)
        self._interval = max(0.1, float(interval))
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._warned = False

    # ------------------------------------------------------------------
    def start(self) -> None:
        """Start emitting heartbeat touches."""

        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._ensure_paths()
            self._write_heartbeat()
            self._thread = threading.Thread(target=self._run, name="HeartbeatWriter", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Stop the heartbeat thread."""

        with self._lock:
            self._stop_event.set()
            thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=self._interval * 2)
        with self._lock:
            self._thread = None

    # ------------------------------------------------------------------
    def _run(self) -> None:
        while not self._stop_event.wait(self._interval):
            self._write_heartbeat()

    # ------------------------------------------------------------------
    def _ensure_paths(self) -> None:
        directory = self._file_path.parent
        try:
            directory.mkdir(mode=0o777, parents=True, exist_ok=True)
            os.chmod(directory, 0o777)
        except Exception as exc:
            log.debug("Failed to ensure heartbeat directory %s: %s", directory, exc)
        if not self._file_path.exists():
            try:
                self._touch_file()
            except Exception as exc:
                log.debug("Failed to create heartbeat file %s: %s", self._file_path, exc)
        try:
            os.chmod(self._file_path, 0o666)
        except Exception:
            # Best effort, permissions might not be changeable for non-root user
            pass

    def _write_heartbeat(self) -> None:
        try:
            self._touch_file()
            if self._warned:
                self._warned = False
        except Exception as exc:
            if not self._warned:
                log.warning("No se pudo escribir heartbeat en %s: %s", self._file_path, exc)
                self._warned = True

    def _touch_file(self) -> None:
        payload = f"{time.time():.6f}\n"
        with open(self._file_path, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())

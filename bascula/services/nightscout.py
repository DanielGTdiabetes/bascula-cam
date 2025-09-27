"""Lightweight Nightscout polling helpers."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

import requests  # type: ignore

from ..config.settings import DiabetesSettings

log = logging.getLogger(__name__)


@dataclass
class NightscoutReading:
    glucose_mgdl: int
    direction: str
    timestamp: float


class NightscoutService:
    """Periodically fetch Nightscout data and trigger alarms."""

    def __init__(self, settings: DiabetesSettings) -> None:
        self.settings = settings
        self._reading: Optional[NightscoutReading] = None
        self._listener: Optional[Callable[[NightscoutReading], None]] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def set_listener(self, callback: Callable[[NightscoutReading], None]) -> None:
        self._listener = callback
        if self._reading and callback:
            callback(self._reading)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        if not self.settings.diabetes_enabled or not self.settings.ns_url:
            log.info("Nightscout disabled")
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)

    def latest(self) -> Optional[NightscoutReading]:
        return self._reading

    # ------------------------------------------------------------------
    def _loop(self) -> None:  # pragma: no cover - thread logic
        log.info("Nightscout polling started")
        while not self._stop.is_set():
            try:
                self._reading = self._fetch()
                if self._reading and self._listener:
                    self._listener(self._reading)
            except Exception:
                log.debug("Nightscout request failed", exc_info=True)
            self._stop.wait(60.0)
        log.info("Nightscout polling stopped")

    def _fetch(self) -> Optional[NightscoutReading]:
        base = self.settings.ns_url.rstrip("/")
        if not base:
            return None
        url = f"{base}/api/v1/entries.json?count=1"
        headers = {"Accept": "application/json"}
        if self.settings.ns_token:
            headers["API-SECRET"] = self.settings.ns_token
        resp = requests.get(url, headers=headers, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list) or not data:
            return None
        entry = data[0]
        glucose = int(float(entry.get("sgv") or entry.get("glucose") or 0))
        direction = str(entry.get("direction") or entry.get("trend") or "Flat")
        timestamp = time.time()
        reading = NightscoutReading(glucose_mgdl=glucose, direction=direction, timestamp=timestamp)
        self._check_alarms(reading)
        return reading

    def _check_alarms(self, reading: NightscoutReading) -> None:
        if not self.settings.diabetes_enabled:
            return
        if reading.glucose_mgdl <= self.settings.hypo_alarm:
            log.warning("Glucose below threshold: %s", reading.glucose_mgdl)
        elif reading.glucose_mgdl >= self.settings.hyper_alarm:
            log.warning("Glucose above threshold: %s", reading.glucose_mgdl)


__all__ = ["NightscoutService", "NightscoutReading"]

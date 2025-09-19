"""Serial scale service with simulation fallback."""
from __future__ import annotations

import contextlib
import logging
import random
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List

try:  # Optional dependency on pyserial
    import serial  # type: ignore
except Exception:  # pragma: no cover - pyserial may be absent in CI
    serial = None  # type: ignore

logger = logging.getLogger("bascula.core.scale")


@dataclass
class ScaleReading:
    timestamp: float
    grams: float


class _BaseScaleDevice:
    def read_grams(self) -> float:
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - default noop
        pass


class _SerialScaleDevice(_BaseScaleDevice):
    def __init__(self, port: str, baudrate: int) -> None:
        if serial is None:
            raise RuntimeError("pyserial no disponible")
        self._serial = serial.Serial(port=port, baudrate=baudrate, timeout=1)
        logger.info("Conectada báscula serie en %s", port)

    def read_grams(self) -> float:
        raw = self._serial.readline().decode(errors="ignore").strip()
        if not raw:
            raise RuntimeError("Lectura vacía de la báscula")
        try:
            return float(raw)
        except ValueError as exc:  # pragma: no cover - depende del firmware
            raise RuntimeError(f"Dato inválido de báscula: {raw!r}") from exc

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self._serial.close()


class _SimulatedScaleDevice(_BaseScaleDevice):
    """Produce lecturas suaves que convergen a un peso objetivo."""

    def __init__(self) -> None:
        self._current = 0.0
        self._target = 0.0
        self._last_change = time.time()

    def read_grams(self) -> float:
        now = time.time()
        if now - self._last_change > random.uniform(5.0, 15.0):
            self._target = random.choice([0.0, random.uniform(25.0, 420.0)])
            self._last_change = now
        diff = self._target - self._current
        step = max(0.2, abs(diff) * 0.15)
        noise = random.uniform(-0.4, 0.4)
        if diff > 0:
            self._current = min(self._target, self._current + step + noise)
        else:
            self._current = max(self._target, self._current - step + noise)
        self._current = max(0.0, self._current)
        return round(self._current + random.uniform(-0.25, 0.25), 3)


class ScaleService:
    """Read weights from a serial device with stability detection."""

    def __init__(self, *, port: str = "/dev/serial0", baudrate: int = 115200) -> None:
        self._lock = threading.Lock()
        self._listeners: List[Callable[[bool], None]] = []
        self._readings: List[ScaleReading] = []
        self._tare_offset = 0.0
        self._stable = False
        self._running = True
        self._device = self._open_device(port, baudrate)
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()
        logger.info("Servicio de báscula iniciado (%s)", type(self._device).__name__)

    def _open_device(self, port: str, baudrate: int) -> _BaseScaleDevice:
        if serial is not None and Path(port).exists():
            try:
                return _SerialScaleDevice(port, baudrate)
            except Exception:
                logger.warning("Fallo al abrir puerto serie %s; usando simulación", port, exc_info=True)
        else:
            logger.info("Puerto %s no disponible; activando simulador", port)
        return _SimulatedScaleDevice()

    # Public API ---------------------------------------------------------
    def read_weight(self) -> float:
        with self._lock:
            value = self._readings[-1].grams if self._readings else 0.0
        return round(max(0.0, value - self._tare_offset), 2)

    def tare(self) -> None:
        with self._lock:
            current = self._readings[-1].grams if self._readings else 0.0
            self._tare_offset = current
            self._readings.clear()
            logger.info("Aplicada tara: %.2f", self._tare_offset)

    def zero(self) -> None:
        with self._lock:
            self._tare_offset = 0.0
            self._readings.clear()
            logger.info("Báscula puesta a cero")

    @property
    def stable(self) -> bool:
        with self._lock:
            return self._stable

    def add_stability_listener(self, callback: Callable[[bool], None]) -> None:
        self._listeners.append(callback)

    def shutdown(self) -> None:
        self._running = False
        self._thread.join(timeout=2.0)
        with contextlib.suppress(Exception):
            self._device.close()

    # Internal machinery -------------------------------------------------
    def _poll_loop(self) -> None:
        history_window = 1.5  # seconds
        while self._running:
            timestamp = time.time()
            try:
                raw = self._device.read_grams()
            except Exception:
                logger.warning("Lectura inválida de báscula", exc_info=True)
                time.sleep(0.5)
                continue
            with self._lock:
                self._readings.append(ScaleReading(timestamp, raw))
                cutoff = timestamp - history_window
                self._readings = [reading for reading in self._readings if reading.timestamp >= cutoff]
                new_stable = self._compute_stable_locked()
                if new_stable != self._stable:
                    self._stable = new_stable
                    for callback in list(self._listeners):
                        try:
                            callback(self._stable)
                        except Exception:
                            logger.exception("Error notificando estabilidad")
            time.sleep(0.2)

    def _compute_stable_locked(self) -> bool:
        if len(self._readings) < 3:
            return False
        values = [reading.grams for reading in self._readings]
        if max(values) - min(values) > 1.0:
            return False
        newest = self._readings[-1]
        oldest = self._readings[0]
        return newest.timestamp - oldest.timestamp >= 0.8


__all__ = ["ScaleService", "ScaleReading"]

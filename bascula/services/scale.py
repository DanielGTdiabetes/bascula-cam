# -*- coding: utf-8 -*-
"""Robust wrapper around the hardware scale backend.

This module exposes a :class:`ScaleService` that orchestrates the serial
backend running on an ESP32 (``python_backend/serial_scale.py``).  The focus is
on resiliency: configuration is pulled from environment variables or INI files,
all hardware failures are logged without crashing the UI and a
``NullScaleService`` provides a safe fallback when the device is unavailable.

The service owns its own worker thread and therefore never blocks the Tk main
loop.  Readings are debounced and optionally smoothed using a small moving
average window which can be configured through ``BASCULA_FILTER_WINDOW`` or the
``[scale]`` section in ``/etc/bascula/config.ini``.  Whenever the serial port
disappears the worker attempts to reconnect using an exponential backoff with a
maximum delay of five seconds.
"""

from __future__ import annotations

import configparser
import logging
import os
import queue
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Callable, Optional

# ---------------------------------------------------------------------------
# Locate ``python_backend`` so importing ``serial_scale`` keeps working when the
# service is executed from scripts/tools instead of the packaged application.

REPO_ROOT = Path(__file__).resolve().parents[2]
PY_BACKEND = REPO_ROOT / "python_backend"
if str(PY_BACKEND) not in sys.path:
    sys.path.insert(0, str(PY_BACKEND))

try:  # pragma: no cover - import may fail on dev machines without the backend
    from serial_scale import SerialScale  # type: ignore
except Exception:  # pragma: no cover
    SerialScale = None  # type: ignore


_DEFAULT_DEVICES: tuple[str, ...] = (
    "/dev/bascula",
    "/dev/ttyUSB0",
    "/dev/ttyUSB1",
    "/dev/ttyACM0",
    "/dev/ttyACM1",
    "/dev/serial0",
    "/dev/i2c-1",
)

_CONFIG_PATHS: tuple[Path, ...] = (
    Path("/etc/bascula/config.ini"),
    Path.home() / ".config" / "bascula" / "config.ini",
    REPO_ROOT / "etc" / "bascula" / "config.ini",
)


def _read_ini_option(section: str, option: str) -> Optional[str]:
    parser = configparser.ConfigParser()
    for path in _CONFIG_PATHS:
        try:
            if not path.exists():
                continue
            parser.read(path, encoding="utf-8")
            if parser.has_option(section, option):
                return parser.get(section, option).strip()
        except Exception:
            continue
    return None


class NullScaleService:
    """Safe fallback object returned when the real hardware is unavailable."""

    name = "null"

    def __init__(self, reason: str = "", logger: Optional[logging.Logger] = None) -> None:
        self.logger = logger or logging.getLogger(__name__)
        self.device: Optional[str] = None
        self.is_null = True
        self._reason = reason
        if reason:
            self.logger.info("ScaleService en modo seguro: %s", reason)

    # Public API ---------------------------------------------------------
    def start(self) -> bool:
        return True

    def stop(self) -> None:
        return None

    def get_weight(self) -> float:
        return 0.0

    def tare(self) -> bool:
        return True

    def on_tick(self, _cb: Callable[[float, bool], None]) -> None:
        return None

    def is_stable(self) -> bool:
        return False

    def drain_readings(self) -> list[tuple[float, bool]]:
        return []


class ScaleService:
    """High level abstraction for the ESP32 based scale."""

    name = "serial"

    def __init__(
        self,
        *,
        device: Optional[str] = None,
        baud: int = 115200,
        sample_ms: Optional[int] = None,
        filter_window: Optional[int] = None,
        debounce_g: Optional[float] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.logger = logger or logging.getLogger(__name__)
        if SerialScale is None:
            raise RuntimeError("Backend serial_scale no disponible")

        env_device = os.getenv("BASCULA_DEVICE", "").strip()
        ini_device = _read_ini_option("scale", "device") or None
        chosen_device = device or env_device or ini_device

        env_filter = os.getenv("BASCULA_FILTER_WINDOW", "").strip()
        env_sample = os.getenv("BASCULA_SAMPLE_MS", "").strip()
        env_debounce = os.getenv("BASCULA_DEBOUNCE_G", "").strip()

        filter_window = filter_window or (int(env_filter) if env_filter.isdigit() else None)
        sample_ms = sample_ms or (int(env_sample) if env_sample.isdigit() else None)
        try:
            debounce_g = debounce_g if debounce_g is not None else (float(env_debounce) if env_debounce else None)
        except ValueError:
            debounce_g = None

        if filter_window is None:
            ini_filter = _read_ini_option("scale", "filter_window")
            if ini_filter and ini_filter.isdigit():
                filter_window = int(ini_filter)
        if sample_ms is None:
            ini_sample = _read_ini_option("scale", "sample_ms")
            if ini_sample and ini_sample.isdigit():
                sample_ms = int(ini_sample)
        if debounce_g is None:
            ini_debounce = _read_ini_option("scale", "debounce_g")
            if ini_debounce:
                try:
                    debounce_g = float(ini_debounce)
                except ValueError:
                    pass

        self.baud = int(baud)
        self.device, self._device_reason = self._resolve_device(chosen_device, ini_device, env_device)
        if self.device is None:
            raise RuntimeError("No se encontró dispositivo de báscula")

        self.logger.info("Báscula usando %s (%s)", self.device, self._device_reason)

        self.is_null = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._backend: Optional[SerialScale] = None  # type: ignore[assignment]
        self._callbacks: list[Callable[[float, bool], None]] = []
        self._queue: queue.Queue[tuple[float, bool]] = queue.Queue(maxsize=1)
        self._lock = threading.Lock()
        self._last_weight = 0.0
        self._last_stable = False
        self._last_reported = 0.0
        self._sample_interval = max(0.05, (sample_ms or 200) / 1000.0)
        window = max(1, filter_window or 1)
        self._ma = deque(maxlen=window)
        self._debounce = max(0.0, debounce_g or 0.0)

    # ------------------------------------------------------------------ Creation
    @classmethod
    def safe_create(cls, **kwargs) -> "ScaleService | NullScaleService":
        logger = kwargs.get("logger") or logging.getLogger(__name__)
        try:
            return cls(**kwargs)
        except Exception as exc:
            logger.warning("ScaleService fallback", exc_info=True)
            return NullScaleService(reason=str(exc), logger=logger)

    # ------------------------------------------------------------------ Lifecycle
    def start(self) -> bool:
        if self._thread and self._thread.is_alive():
            return True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._worker, name="ScaleService", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop_event.set()
        backend = self._backend
        if backend is not None:
            try:
                backend.stop()
            except Exception:
                self.logger.debug("Error deteniendo backend", exc_info=True)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None
        self._backend = None

    # ------------------------------------------------------------------ Data API
    def get_weight(self) -> float:
        with self._lock:
            return float(self._last_weight)

    def is_stable(self) -> bool:
        with self._lock:
            return bool(self._last_stable)

    def tare(self) -> bool:
        backend = self._backend
        if backend is None:
            return False

        action = getattr(backend, "tare", None)
        if not callable(action):
            return False

        try:
            result = action()
        except Exception:
            self.logger.warning("No se pudo enviar comando de tara a la báscula", exc_info=True)
            return False
        return bool(result)

    def on_tick(self, callback: Callable[[float, bool], None]) -> None:
        if not callable(callback):
            return
        self._callbacks.append(callback)

    # ------------------------------------------------------------------ Internals
    def _resolve_device(
        self,
        chosen: Optional[str],
        ini_device: Optional[str],
        env_device: str,
    ) -> tuple[Optional[str], str]:
        if chosen:
            path = Path(chosen)
            if path.exists():
                resolved = str(path.resolve())
                reason = "parámetro"
                if env_device and Path(env_device).exists() and resolved == str(Path(env_device).resolve()):
                    reason = "BASCULA_DEVICE"
                elif ini_device and Path(ini_device).exists() and resolved == str(Path(ini_device).resolve()):
                    reason = "config.ini"
                return str(path), reason
            self.logger.warning("Dispositivo configurado %s no existe", chosen)

        tried: set[str] = set()
        ordered: list[tuple[str, str]] = []
        if env_device:
            ordered.append((env_device, "BASCULA_DEVICE"))
        if ini_device and ini_device != env_device:
            ordered.append((ini_device, "config.ini"))
        ordered.extend((dev, "autodetect") for dev in _DEFAULT_DEVICES)

        for candidate, origin in ordered:
            if not candidate or candidate in tried:
                continue
            tried.add(candidate)
            path = Path(candidate)
            if path.exists():
                return candidate, origin
        return None, "sin_dispositivo"

    def _worker(self) -> None:
        backoff = 0.5
        while not self._stop_event.is_set():
            try:
                backend = SerialScale(self.device, baudrate=self.baud, logger=self.logger)  # type: ignore[arg-type]
            except Exception as exc:
                self.logger.warning("No se puede abrir %s: %s", self.device, exc)
                if self._stop_event.wait(min(backoff, 5.0)):
                    break
                backoff = min(backoff * 2, 5.0)
                continue

            backoff = 0.5
            self._backend = backend
            try:
                backend.start(self._on_backend_tick)
                self.logger.info("Backend de báscula iniciado")
                while not self._stop_event.wait(self._sample_interval):
                    thread = getattr(backend, "_thread", None)
                    if thread is not None and not thread.is_alive():
                        raise RuntimeError("Hilo de báscula detenido")
            except Exception:
                self.logger.warning("Error en backend de báscula", exc_info=True)
            finally:
                try:
                    backend.stop()
                except Exception:
                    pass
                self._backend = None
                if self._stop_event.is_set():
                    break
                if self._stop_event.wait(min(backoff, 5.0)):
                    break
                backoff = min(backoff * 2, 5.0)

    def _on_backend_tick(self, grams: float, stable: int) -> None:
        try:
            weight = float(grams)
            is_stable = bool(int(stable))
        except Exception:
            return

        self._ma.append(weight)
        filtered = sum(self._ma) / len(self._ma) if self._ma else weight

        if self._debounce > 0 and abs(filtered - self._last_reported) < self._debounce:
            return

        with self._lock:
            self._last_weight = filtered
            self._last_stable = is_stable
        self._last_reported = filtered

        try:
            self._queue.put_nowait((filtered, is_stable))
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait((filtered, is_stable))
            except queue.Full:
                pass

        for cb in list(self._callbacks):
            try:
                cb(filtered, is_stable)
            except Exception:
                self.logger.debug("Callback de báscula lanzó excepción", exc_info=True)

    # Utilities ----------------------------------------------------------
    def drain_readings(self) -> list[tuple[float, bool]]:
        drained: list[tuple[float, bool]] = []
        while True:
            try:
                drained.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return drained


__all__ = ["ScaleService", "NullScaleService"]


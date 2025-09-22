"""Thread-safe high level scale service with dummy fallback."""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, List, Optional

from bascula.core.scale_serial import SerialScale

LOGGER = logging.getLogger("bascula.scale")


class ScaleService:
    """Background reader exposing current net weight in grams."""

    def __init__(
        self,
        port: Optional[str] = None,
        *,
        baud: int = 115200,
        decimals: int = 0,
        density: float = 1.0,
        logger: Optional[logging.Logger] = None,
        simulate_if_unavailable: Optional[bool] = None,
        fail_fast: bool = False,
        **legacy_kwargs: object,
    ) -> None:
        self.logger = logger or LOGGER
        self._decimals = max(0, int(decimals))
        self._density = float(density) if density else 1.0
        self._lock = threading.Lock()
        self._net_weight = 0.0
        self._gross_weight = 0.0
        self._stable = False
        self._subs: List[Callable[[float, bool], None]] = []
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        device = legacy_kwargs.get("device") if port is None else port
        if device == "__dummy__":
            device = None
            simulate_if_unavailable = True

        baudrate = int(legacy_kwargs.get("baudrate") or legacy_kwargs.get("baud") or baud)

        if simulate_if_unavailable is None:
            simulate_if_unavailable = not fail_fast

        try:
            self._scale = SerialScale(
                device=device,
                baudrate=baudrate,
                simulate_if_unavailable=simulate_if_unavailable,
                logger=self.logger,
            )
            self._scale.start()
        except Exception as exc:
            if fail_fast:
                raise
            self.logger.warning("Falling back to simulated scale: %s", exc)
            self._scale = SerialScale(
                device=None,
                simulate_if_unavailable=True,
                logger=self.logger,
            )
            self._scale.start()

        self.start()

    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="ScaleService", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None
        try:
            self._scale.stop()
        except Exception:  # pragma: no cover - hardware dependent
            pass

    close = stop  # backwards compatibility

    # ------------------------------------------------------------------
    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                net = float(self._scale.read_weight())
                try:
                    gross = float(self._scale.read_gross())
                except Exception:
                    gross = net
                stable = bool(getattr(self._scale, "stable", False))
                rounded_net = round(net, self._decimals)
                rounded_gross = round(gross, self._decimals)
                with self._lock:
                    self._net_weight = rounded_net
                    self._gross_weight = rounded_gross
                    self._stable = stable
                for callback in list(self._subs):
                    try:
                        callback(rounded_net, stable)
                    except Exception:  # pragma: no cover - subscriber safety
                        self.logger.exception("Scale subscriber failed")
                time.sleep(0.1)
            except Exception as exc:
                self.logger.debug("Scale read failed: %s", exc)
                time.sleep(0.3)

    # ------------------------------------------------------------------
    @property
    def net_weight(self) -> float:
        with self._lock:
            return float(self._net_weight)

    @property
    def density(self) -> float:
        with self._lock:
            return float(self._density)

    @density.setter
    def density(self, value: float) -> None:
        with self._lock:
            self._density = float(value) if value else 1.0

    def get_weight(self) -> float:
        return self.net_weight

    def is_stable(self) -> bool:
        with self._lock:
            return bool(self._stable)

    # ------------------------------------------------------------------
    def tare(self) -> None:
        try:
            self._scale.tare()
        except Exception as exc:  # pragma: no cover - hardware dependent
            self.logger.warning("tare() failed: %s", exc)

    def zero(self) -> None:
        try:
            self._scale.zero()
        except Exception as exc:  # pragma: no cover - hardware dependent
            self.logger.warning("zero() failed: %s", exc)

    def send_command(self, command: str) -> None:
        try:
            self._scale.send_command(command)
        except Exception as exc:  # pragma: no cover - hardware dependent
            self.logger.warning("send_command(%s) failed: %s", command, exc)

    # ------------------------------------------------------------------
    def subscribe(self, callback: Callable[[float, bool], None]) -> None:
        if callable(callback):
            self._subs.append(callback)


HX711Service = ScaleService

__all__ = ["ScaleService", "HX711Service"]

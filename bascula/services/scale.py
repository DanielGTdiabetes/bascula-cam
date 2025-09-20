# -*- coding: utf-8 -*-
"""High level scale service wrapping :mod:`bascula.core.scale_serial`."""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, List, Optional

from bascula.core.scale_serial import SerialScale


class ScaleService:
    """Thread-safe wrapper over :class:`SerialScale` with subscriber support."""

    def __init__(
        self,
        device: str | None = None,
        baud: int | None = None,
        *,
        baudrate: int | None = None,
        logger: Optional[logging.Logger] = None,
        fail_fast: bool = True,
        calibration_factor: float = 1.0,
        simulate_if_unavailable: Optional[bool] = None,
        **_: object,
    ) -> None:
        self.logger = logger or logging.getLogger("bascula.scale")
        self.logger.debug("Initialising ScaleService")

        if simulate_if_unavailable is None:
            simulate_if_unavailable = not fail_fast

        baud_candidate = baudrate if baudrate is not None else baud
        self._scale = SerialScale(
            device=device,
            baudrate=baud_candidate,
            simulate_if_unavailable=simulate_if_unavailable,
            logger=self.logger,
        )

        self._calibration_factor = max(0.0001, float(calibration_factor))
        self._subs: List[Callable[[float, bool], None]] = []
        self._lock = threading.Lock()
        self._last_raw: float = 0.0
        self._last_weight: float = 0.0
        self._last_stable: bool = False

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self._fail_fast = bool(fail_fast)

    # ------------------------------------------------------------------
    def start(self) -> None:
        try:
            self._scale.start()
        except Exception:
            if self._fail_fast:
                raise
            self.logger.exception("Falling back to simulation mode")
            self._scale = SerialScale(
                simulate_if_unavailable=True,
                logger=self.logger,
            )
            self._scale.start()

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
        self._scale.stop()

    # ------------------------------------------------------------------
    def _run_loop(self) -> None:
        poll_interval = 0.08
        last_notified_weight = None
        last_notified_stable = None
        while not self._stop_event.is_set():
            try:
                raw = self._scale.read_weight()
                stable = self._scale.stable
                calibrated = max(0.0, raw * self._calibration_factor)
                with self._lock:
                    self._last_raw = raw
                    self._last_weight = calibrated
                    self._last_stable = stable
                if (
                    last_notified_weight is None
                    or abs(calibrated - last_notified_weight) > 0.05
                    or bool(stable) != bool(last_notified_stable)
                ):
                    last_notified_weight = calibrated
                    last_notified_stable = stable
                    for cb in list(self._subs):
                        try:
                            cb(calibrated, bool(stable))
                        except Exception as exc:  # pragma: no cover
                            self.logger.warning("Subscriber error: %s", exc)
                time.sleep(poll_interval)
            except Exception as exc:  # pragma: no cover - safeguard
                self.logger.debug("ScaleService loop error: %s", exc)
                time.sleep(0.2)

    # ------------------------------------------------------------------
    def get_weight(self) -> float:
        with self._lock:
            return float(self._last_weight)

    def get_latest(self) -> float:
        with self._lock:
            return float(self._last_raw)

    def is_stable(self) -> bool:
        with self._lock:
            return bool(self._last_stable)

    # ------------------------------------------------------------------
    def tare(self) -> bool:
        try:
            self._scale.tare()
            return True
        except Exception as exc:  # pragma: no cover - hardware
            self.logger.warning("tare() failed: %s", exc)
            return False

    def zero(self) -> bool:
        try:
            self._scale.zero()
            return True
        except Exception as exc:  # pragma: no cover - hardware
            self.logger.warning("zero() failed: %s", exc)
            return False

    def send_command(self, command: str) -> None:
        try:
            self._scale.send_command(command)
        except Exception as exc:  # pragma: no cover - hardware
            self.logger.warning("send_command(%s) failed: %s", command, exc)

    # ------------------------------------------------------------------
    def set_calibration_factor(self, factor: float) -> None:
        with self._lock:
            self._calibration_factor = max(0.0001, float(factor))

    def get_calibration_factor(self) -> float:
        with self._lock:
            return float(self._calibration_factor)

    def calibrate(self, weight_grams: float) -> bool:
        try:
            self._scale.send_command(f"C:{float(weight_grams):.3f}")
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    def subscribe(self, cb: Callable[[float, bool], None]) -> None:
        if callable(cb):
            self._subs.append(cb)


HX711Service = ScaleService

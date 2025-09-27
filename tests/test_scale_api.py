"""API level tests for the scale service."""

from __future__ import annotations

import queue
import time

import pytest

from bascula.config.settings import ScaleSettings
from bascula.services import scale


class ControlledBackend(scale.BaseScaleBackend):
    name = "CONTROLLED"

    def __init__(self) -> None:
        self.samples: "queue.Queue[float]" = queue.Queue()
        self._current = 0.0

    def read(self) -> float:
        try:
            self._current = self.samples.get_nowait()
        except queue.Empty:
            pass
        return self._current


def _wait_for(queue_: "queue.Queue[tuple[float, bool, str]]", predicate, timeout: float = 1.5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        remaining = max(0.0, deadline - time.monotonic())
        try:
            value = queue_.get(timeout=remaining)
        except queue.Empty:
            break
        if predicate(value):
            return value
    raise AssertionError("no matching value received")


def test_scale_service_api(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = ControlledBackend()
    backend.samples.put(100.0)

    monkeypatch.setattr(scale.ScaleService, "_select_backend", lambda self: backend)
    settings = ScaleSettings(calib_factor=2.0, smoothing=1, decimals=0)
    service = scale.ScaleService(settings, logger=scale.LOGGER)
    updates: "queue.Queue[tuple[float, bool, str]]" = queue.Queue()

    def callback(value: float, stable: bool, unit: str = "g") -> None:
        updates.put((value, stable, unit))

    service.subscribe(callback)

    first = _wait_for(updates, lambda v: v[0] > 0 and v[2] == "g")
    assert first[0] == pytest.approx(50.0)

    service.tare()
    backend.samples.put(150.0)
    second = _wait_for(updates, lambda v: v[0] != first[0] and v[2] == "g")
    assert second[0] == pytest.approx(25.0)

    service.zero()
    backend.samples.put(200.0)
    third = _wait_for(updates, lambda v: v[2] == "g" and v[0] >= 99.0)
    assert third[0] == pytest.approx(100.0)
    assert service.get_last_weight_g() == pytest.approx(100.0)

    service.set_decimals(1)
    service.set_ml_factor(2.0)
    unit = service.toggle_units()
    assert unit == "ml"
    fourth = _wait_for(updates, lambda v: v[2] == "ml")
    assert fourth[0] == pytest.approx(50.0)

    assert service.get_calibration_factor() == pytest.approx(2.0)
    service.set_calibration_factor(4.0)
    assert service.get_calibration_factor() == pytest.approx(4.0)

    try:
        backend.samples.put(600.0)
        fifth = _wait_for(updates, lambda v: v[2] == "ml" and v[0] > fourth[0])
        assert fifth[0] == pytest.approx(75.0)
    finally:
        service.stop()

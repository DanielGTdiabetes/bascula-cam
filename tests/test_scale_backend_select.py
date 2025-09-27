"""Backend selection logic for the scale service."""

from __future__ import annotations

import logging

import pytest

from bascula.config.settings import ScaleSettings
from bascula.services import scale


class _DummyBackend(scale.BaseScaleBackend):
    name = "DUMMY"

    def __init__(self) -> None:
        self.read_count = 0

    def read(self) -> float:
        self.read_count += 1
        return 0.0


def test_hx711_selected_when_port_dummy(monkeypatch: pytest.MonkeyPatch) -> None:
    created = {}

    class FakeHX(_DummyBackend):
        name = "HX711_GPIO"

        def __init__(self, dt_pin: int, sck_pin: int, **_: object) -> None:
            super().__init__()
            created["pins"] = (dt_pin, sck_pin)

    monkeypatch.setattr(scale, "HX711GpioBackend", FakeHX)

    def _raise_serial(*args, **kwargs):
        raise scale.BackendUnavailable("serial")

    monkeypatch.setattr(scale, "SerialScaleBackend", _raise_serial)
    settings = ScaleSettings(port="__dummy__", hx711_dt=21, hx711_sck=20, smoothing=1)
    service = scale.ScaleService(settings, logger=logging.getLogger("test.scale"))
    try:
        assert isinstance(service._backend, FakeHX)  # type: ignore[attr-defined]
        assert created["pins"] == (21, 20)
    finally:
        service.stop()


def test_serial_failure_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingSerial:
        def __init__(self, *args, **kwargs) -> None:
            raise scale.BackendUnavailable("no serial")

    class FailingHX:
        def __init__(self, *args, **kwargs) -> None:
            raise scale.BackendUnavailable("no gpio")

    monkeypatch.setattr(scale, "SerialScaleBackend", FailingSerial)
    monkeypatch.setattr(scale, "HX711GpioBackend", FailingHX)
    settings = ScaleSettings(port="/dev/ttyFAKE", smoothing=1)
    service = scale.ScaleService(settings, logger=logging.getLogger("test.scale"))
    try:
        assert isinstance(service._backend, scale.SimulatedScaleBackend)  # type: ignore[attr-defined]
    finally:
        service.stop()

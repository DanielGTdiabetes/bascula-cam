from __future__ import annotations

import logging

import pytest

from bascula.services import scale


class FakeLgpio:
    def __init__(self) -> None:
        self.handle = 12

    def gpiochip_open(self, chip: int) -> int:
        return self.handle

    def gpio_claim_input(self, handle: int, pin: int) -> None:  # pragma: no cover - simple stub
        return None

    def gpio_claim_output(self, handle: int, pin: int, value: int) -> None:  # pragma: no cover - simple stub
        return None

    def gpio_write(self, handle: int, pin: int, value: int) -> None:  # pragma: no cover - simple stub
        return None

    def gpio_free(self, handle: int, pin: int) -> None:  # pragma: no cover - simple stub
        return None

    def gpiochip_close(self, handle: int) -> None:  # pragma: no cover - simple stub
        return None


def test_scale_backend_logs_initialisation(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    fake_gpio = FakeLgpio()
    monkeypatch.setattr(scale, "lgpio", fake_gpio)

    logger = logging.getLogger("test.scale.logs")
    caplog.set_level(logging.INFO, logger="test.scale.logs")

    backend = scale.HX711GpioBackend(5, 6, logger=logger)
    try:
        messages = [record.message for record in caplog.records]
        assert (
            "Scale backend: HX711_GPIO (lgpio) inicializado (chip=0, dt=5, sck=6)" in messages
        )
    finally:
        backend.stop()

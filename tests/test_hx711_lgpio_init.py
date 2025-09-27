from __future__ import annotations

import logging

import pytest

from bascula.services import scale


class FakeLgpio:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple]] = []
        self.handle = 42

    def gpiochip_open(self, chip: int) -> int:
        self.calls.append(("open", (chip,)))
        return self.handle

    def gpio_claim_input(self, handle: int, pin: int) -> None:
        self.calls.append(("claim_input", (handle, pin)))

    def gpio_claim_output(self, handle: int, pin: int, value: int) -> None:
        self.calls.append(("claim_output", (handle, pin, value)))

    def gpio_write(self, handle: int, pin: int, value: int) -> None:
        self.calls.append(("write", (handle, pin, value)))

    def gpio_free(self, handle: int, pin: int) -> None:
        self.calls.append(("free", (handle, pin)))

    def gpiochip_close(self, handle: int) -> None:
        self.calls.append(("close", (handle,)))


def test_hx711_lgpio_initialisation(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    fake_gpio = FakeLgpio()
    monkeypatch.setattr(scale, "lgpio", fake_gpio)

    logger = logging.getLogger("test.scale.hx711")
    caplog.set_level(logging.INFO, logger="test.scale.hx711")

    backend = scale.HX711GpioBackend(5, 6, logger=logger)

    try:
        assert ("open", (0,)) in fake_gpio.calls
        assert ("claim_input", (fake_gpio.handle, 5)) in fake_gpio.calls
        assert ("claim_output", (fake_gpio.handle, 6, 0)) in fake_gpio.calls

        messages = [record.message for record in caplog.records]
        assert (
            "Scale backend: HX711_GPIO (lgpio) inicializado (chip=0, dt=5, sck=6)" in messages
        )
    finally:
        backend.stop()

    assert ("write", (fake_gpio.handle, 6, 0)) in fake_gpio.calls
    assert ("free", (fake_gpio.handle, 6)) in fake_gpio.calls
    assert ("free", (fake_gpio.handle, 5)) in fake_gpio.calls
    assert ("close", (fake_gpio.handle,)) in fake_gpio.calls

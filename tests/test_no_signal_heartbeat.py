from __future__ import annotations

import logging
import queue
import time

import pytest

from bascula.config.settings import ScaleSettings
from bascula.services import scale


class NoSignalLgpio:
    def __init__(self) -> None:
        self.handle = 21

    def gpiochip_open(self, chip: int) -> int:
        return self.handle

    def gpio_claim_input(self, handle: int, pin: int) -> None:  # pragma: no cover - simple mock
        pass

    def gpio_claim_output(self, handle: int, pin: int, value: int) -> None:  # pragma: no cover - simple mock
        pass

    def gpio_read(self, handle: int, pin: int) -> int:
        return 1  # DT line never goes low

    def gpio_write(self, handle: int, pin: int, value: int) -> None:  # pragma: no cover - simple mock
        pass

    def gpio_free(self, handle: int, pin: int) -> None:  # pragma: no cover - simple mock
        pass

    def gpiochip_close(self, handle: int) -> None:  # pragma: no cover - simple mock
        pass


def test_no_signal_generates_none_heartbeats(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(scale, "lgpio", NoSignalLgpio())

    caplog.set_level(logging.WARNING, logger="bascula.scale")
    settings = ScaleSettings(hx711_dt=5, hx711_sck=6, smoothing=1, decimals=0)
    service = scale.ScaleService(settings, logger=scale.LOGGER)

    updates: "queue.Queue[tuple[object, bool, str, float]]" = queue.Queue()

    def callback(value: object, stable: bool, unit: str = "g") -> None:
        updates.put((value, stable, unit, time.monotonic()))

    service.subscribe(callback)

    try:
        deadline = time.monotonic() + 2.5
        collected: list[tuple[object, bool, str, float]] = []
        while time.monotonic() < deadline and len(collected) < 4:
            remaining = max(0.0, deadline - time.monotonic())
            try:
                collected.append(updates.get(timeout=remaining))
            except queue.Empty:
                break

        assert len(collected) >= 3, "expected repeated None heartbeats when HX711 has no data"
        assert all(item[0] is None for item in collected)

        timestamps = [item[3] for item in collected]
        diffs = [b - a for a, b in zip(timestamps, timestamps[1:])]
        assert diffs, "expected more than one heartbeat interval"

        steady_diffs = diffs[1:] if len(diffs) > 1 else diffs
        assert steady_diffs, "expected at least one rate-limited heartbeat"
        for diff in steady_diffs:
            assert diff >= 0.45
            assert diff <= 0.8
        lost_messages = [record.message for record in caplog.records if "Scale: signal LOST" in record.message]
        if lost_messages:
            assert lost_messages[:1] == ["Scale: signal LOST (hx711 no data)"]
            assert lost_messages.count(lost_messages[0]) == 1
    finally:
        service.stop()

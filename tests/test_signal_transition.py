"""Test signal loss and restoration transitions."""

from __future__ import annotations

import queue
import time
from dataclasses import dataclass

import pytest

from bascula.config.settings import ScaleSettings
from bascula.services import scale


class ToggleBackend(scale.BaseScaleBackend):
    name = "TOGGLE"

    def __init__(self) -> None:
        self.mode = "exception"
        self.value = 0.0

    def read(self) -> float:
        if self.mode == "value":
            return self.value
        if self.mode == "none":
            return None  # type: ignore[return-value]
        if self.mode == "exception":
            raise scale.BackendUnavailable("no signal")
        raise AssertionError(f"unknown mode {self.mode}")


@dataclass
class DummyLogger:
    records: list[tuple[str, str]]

    def __init__(self) -> None:
        self.records = []

    def _record(self, level: str, message: str, *args, **kwargs) -> None:
        if args:
            message = message % args
        self.records.append((level, message))

    def info(self, message: str, *args, **kwargs) -> None:
        self._record("INFO", message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs) -> None:
        self._record("WARNING", message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs) -> None:
        self._record("ERROR", message, *args, **kwargs)

    def debug(self, message: str, *args, **kwargs) -> None:
        self._record("DEBUG", message, *args, **kwargs)

    def exception(self, message: str, *args, **kwargs) -> None:
        self.error(message, *args, **kwargs)


def _next_update(
    updates: "queue.Queue[tuple[object, bool, str, float]]",
    predicate,
    timeout: float = 1.0,
) -> tuple[object, bool, str, float]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        remaining = max(0.0, deadline - time.monotonic())
        try:
            value = updates.get(timeout=remaining)
        except queue.Empty:
            break
        if predicate(value):
            return value
    raise AssertionError("no matching update received")


def _drain(updates: "queue.Queue[tuple[object, bool, str, float]]", duration: float) -> list[tuple[object, bool, str, float]]:
    collected: list[tuple[object, bool, str, float]] = []
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        remaining = max(0.0, deadline - time.monotonic())
        try:
            collected.append(updates.get(timeout=remaining))
        except queue.Empty:
            break
    return collected


def test_signal_transition(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = ToggleBackend()
    logger = DummyLogger()
    monkeypatch.setattr(scale.ScaleService, "_select_backend", lambda self: backend)

    settings = ScaleSettings(smoothing=1, decimals=1)
    service = scale.ScaleService(settings, logger=logger)
    service._none_heartbeat_interval = 0.05

    updates: "queue.Queue[tuple[object, bool, str, float]]" = queue.Queue()

    def callback(value: object, stable: bool, unit: str = "g") -> None:
        updates.put((value, stable, unit, time.monotonic()))

    service.subscribe(callback)

    try:
        first_none = _next_update(updates, lambda item: item[0] is None)
        assert first_none[0] is None

        backend.mode = "value"
        backend.value = 50.0
        value_update = _next_update(updates, lambda item: isinstance(item[0], float) and item[0] > 0)
        assert value_update[0] == pytest.approx(50.0)

        restored_logs = [msg for level, msg in logger.records if "Scale: signal RESTORED" in msg]
        assert len(restored_logs) == 1

        # Ensure no stale None events immediately after signal restoration.
        for event in _drain(updates, 0.15):
            assert event[0] is not None

        backend.mode = "exception"
        second_none = _next_update(updates, lambda item: item[0] is None)
        assert second_none[0] is None

        lost_logs = [msg for level, msg in logger.records if "Scale: signal LOST" in msg]
        assert len(lost_logs) == 1

        # No additional logs beyond the single transition entries.
        assert restored_logs.count(restored_logs[0]) == 1
        assert lost_logs.count(lost_logs[0]) == 1
    finally:
        service.stop()

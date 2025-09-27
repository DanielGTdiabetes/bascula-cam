"""Ensure BackendUnavailable produces periodic None heartbeats."""

from __future__ import annotations

import queue
import time

import pytest

from bascula.config.settings import ScaleSettings
from bascula.services import scale


class AlwaysUnavailableBackend(scale.BaseScaleBackend):
    name = "ALWAYS_UNAVAILABLE"

    def read(self) -> float:
        raise scale.BackendUnavailable("no signal")


def _collect_updates(
    updates: "queue.Queue[tuple[object, bool, str, float]]",
    *,
    minimum: int,
    timeout: float,
) -> list[tuple[object, bool, str, float]]:
    collected: list[tuple[object, bool, str, float]] = []
    deadline = time.monotonic() + timeout
    while len(collected) < minimum and time.monotonic() < deadline:
        remaining = max(0.0, deadline - time.monotonic())
        try:
            collected.append(updates.get(timeout=remaining))
        except queue.Empty:
            break
    return collected


def test_backend_unavailable_heartbeat(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = AlwaysUnavailableBackend()
    monkeypatch.setattr(scale.ScaleService, "_select_backend", lambda self: backend)

    settings = ScaleSettings(smoothing=1, decimals=1)
    service = scale.ScaleService(settings, logger=scale.LOGGER)
    service._none_heartbeat_interval = 0.05  # accelerate for the test

    updates: "queue.Queue[tuple[object, bool, str, float]]" = queue.Queue()

    def callback(value: object, stable: bool, unit: str = "g") -> None:
        updates.put((value, stable, unit, time.monotonic()))

    service.subscribe(callback)

    try:
        collected = _collect_updates(updates, minimum=3, timeout=1.0)
        assert len(collected) >= 3, "expected multiple heartbeats when backend unavailable"
        assert all(item[0] is None for item in collected)
        diffs = [b[3] - a[3] for a, b in zip(collected, collected[1:])]
        assert diffs, "expected at least two heartbeat events"
        assert all(diff <= 0.2 for diff in diffs), "heartbeat None events too sparse"
    finally:
        service.stop()

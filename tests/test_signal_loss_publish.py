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


def test_backend_unavailable_publishes_none_with_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = AlwaysUnavailableBackend()
    monkeypatch.setattr(scale.ScaleService, "_select_backend", lambda self: backend)

    settings = ScaleSettings(smoothing=1, decimals=1)
    service = scale.ScaleService(settings, logger=scale.LOGGER)

    updates: "queue.Queue[tuple[object, bool, str, float]]" = queue.Queue()

    def callback(value: object, stable: bool, unit: str = "g") -> None:
        updates.put((value, stable, unit, time.monotonic()))

    service.subscribe(callback)

    try:
        collected: list[tuple[object, bool, str, float]] = []
        deadline = time.monotonic() + 5.0
        while len(collected) < 4 and time.monotonic() < deadline:
            remaining = max(0.0, deadline - time.monotonic())
            try:
                event = updates.get(timeout=remaining)
            except queue.Empty:
                break
            if event[0] is None:
                collected.append(event)

        assert len(collected) >= 3, "expected repeated None heartbeats"
        diffs = [b[3] - a[3] for a, b in zip(collected, collected[1:])]
        # Skip the first diff which may originate from the initial subscribe notification.
        rate_limited_diffs = diffs[1:] if len(diffs) > 1 else []
        assert rate_limited_diffs, "no rate limited heartbeats captured"
        assert all(diff >= 0.45 for diff in rate_limited_diffs)
    finally:
        service.stop()

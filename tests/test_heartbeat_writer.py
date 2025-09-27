from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import pytest

from bascula.runtime import HeartbeatWriter


def _wait_for_mtime_change(path: os.PathLike[str], baseline: float, timeout: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not os.path.exists(path):
            time.sleep(0.01)
            continue
        current = os.stat(path).st_mtime
        if current > baseline:
            return True
        time.sleep(0.01)
    return False


def test_heartbeat_writer_creates_and_updates(tmp_path: Path) -> None:
    heartbeat_path = tmp_path / "run" / "bascula" / "heartbeat"
    writer = HeartbeatWriter(heartbeat_path, interval=0.1)
    writer.start()
    try:
        assert heartbeat_path.exists()
        initial_mtime = heartbeat_path.stat().st_mtime
        assert _wait_for_mtime_change(heartbeat_path, initial_mtime, timeout=0.5)
    finally:
        writer.stop()

    stopped_mtime = heartbeat_path.stat().st_mtime
    time.sleep(0.2)
    assert heartbeat_path.stat().st_mtime == pytest.approx(stopped_mtime, rel=0, abs=0.001)


def test_heartbeat_writer_logs_warning_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    heartbeat_path = tmp_path / "hb"
    writer = HeartbeatWriter(heartbeat_path, interval=0.05)

    call_counter = {"count": 0}

    def fail_touch(self: HeartbeatWriter) -> None:  # type: ignore[override]
        call_counter["count"] += 1
        raise PermissionError("disk full")

    monkeypatch.setattr(HeartbeatWriter, "_touch_file", fail_touch)
    caplog.set_level(logging.WARNING)

    writer.start()
    time.sleep(0.15)
    writer.stop()

    warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "No se pudo escribir heartbeat" in warnings[0].message
    assert call_counter["count"] >= 2

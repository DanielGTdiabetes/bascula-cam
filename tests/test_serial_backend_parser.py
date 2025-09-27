from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from bascula.services import scale


class FakeSerial:
    read_queue: list[bytes] = []

    def __init__(self, path: str, baudrate: int, timeout: float) -> None:
        self.path = path
        self.baudrate = baudrate
        self.timeout = timeout

    def readline(self) -> bytes:
        if FakeSerial.read_queue:
            return FakeSerial.read_queue.pop(0)
        return b""

    def write(self, payload: bytes) -> int:
        return len(payload)

    def close(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _patch_serial(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scale, "serial", SimpleNamespace(Serial=FakeSerial))
    monkeypatch.setattr(scale, "SerialException", Exception)


def test_serial_backend_parses_line(tmp_path, caplog: pytest.LogCaptureFixture) -> None:
    device = tmp_path / "ttyFAKE"
    device.touch()
    FakeSerial.read_queue = [b"  G: 12.34 , S:1  \r\n"]
    caplog.set_level(logging.INFO, logger="bascula.scale")
    backend = scale.SerialScaleBackend(str(device), 115200, logger=scale.LOGGER)
    try:
        value = backend.read()
        assert value == pytest.approx(12.34)
        assert backend.signal_hint is True
        records = [record.message for record in caplog.records if "Serial" in record.message]
        assert any("señal recuperada" in message for message in records)
    finally:
        backend.stop()


def test_serial_backend_logs_loss_after_gap(tmp_path, caplog: pytest.LogCaptureFixture) -> None:
    device = tmp_path / "ttyFAKE"
    device.touch()
    FakeSerial.read_queue = [b"G:1.0,S:1\n"]
    caplog.set_level(logging.DEBUG, logger="bascula.scale")
    backend = scale.SerialScaleBackend(str(device), 9600, logger=scale.LOGGER)
    try:
        assert backend.read() == pytest.approx(1.0)
        backend._last_valid_ts -= 2.0  # type: ignore[attr-defined]
        backend._last_signal_log -= 2.0  # type: ignore[attr-defined]
        FakeSerial.read_queue = [b"noise\n"]
        assert backend.read() is None
        messages = [record.message for record in caplog.records]
        assert any("señal perdida" in message for message in messages)
        assert any("sin datos válidos" in message for message in messages)
    finally:
        backend.stop()

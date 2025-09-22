"""Tests for ScaleService host/device tare modes."""
import logging
from pathlib import Path

import pytest

import bascula.services.scale as scale


class DummyTomliW:
    def __init__(self) -> None:
        self.last_data: dict | None = None

    def dumps(self, data: dict) -> str:  # pragma: no cover - simple serializer for tests
        self.last_data = dict(data)
        lines = []
        for key, value in data.items():
            if isinstance(value, str):
                lines.append(f'{key} = "{value}"')
            else:
                lines.append(f"{key} = {value}")
        return "\n".join(lines)


def _prepare_config(tmp_path: Path, offset: float, tare: float) -> Path:
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    cfg_file = cfg_dir / "scale.toml"
    cfg_file.write_text(
        "\n".join(
            [
                "factor = 1.0",
                "decimals = 0",
                "density = 1.0",
                f"offset = {offset}",
                f"tare = {tare}",
            ]
        )
    )
    return cfg_file


def _make_service(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, host_mode: bool) -> scale.ScaleService:
    cfg_file = _prepare_config(tmp_path, offset=120.0, tare=35.0)
    monkeypatch.setattr(scale, "CFG_DIR", cfg_file.parent)
    monkeypatch.setattr(scale, "CFG_FILE", cfg_file)
    monkeypatch.setattr(scale.ScaleService, "start", lambda self: None)
    monkeypatch.setenv("BASCULA_SCALE_HOST_TARE", "1" if host_mode else "0")
    service = scale.ScaleService(port="__dummy__", logger=logging.getLogger("test.scale"))
    return service


def test_device_mode_ignores_persisted_offsets(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    service = _make_service(monkeypatch, tmp_path, host_mode=False)
    try:
        assert service._host_tare_mode is False  # type: ignore[attr-defined]
        assert service.calibration_offset == pytest.approx(0.0)
        assert service._tare == pytest.approx(0.0)  # type: ignore[attr-defined]

        service._process_sample(50.0)  # type: ignore[attr-defined]
        assert service.net_weight == pytest.approx(50.0)
    finally:
        service.close()


def test_host_mode_applies_persisted_offsets(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    service = _make_service(monkeypatch, tmp_path, host_mode=True)
    try:
        assert service._host_tare_mode is True  # type: ignore[attr-defined]
        assert service.calibration_offset == pytest.approx(120.0)
        assert service._tare == pytest.approx(35.0)  # type: ignore[attr-defined]

        service._process_sample(50.0)  # type: ignore[attr-defined]
        assert service.net_weight == pytest.approx(0.0)

        service.zero()
        assert service.calibration_offset == pytest.approx(50.0)
        assert service._tare == pytest.approx(0.0)  # type: ignore[attr-defined]

        service._process_sample(80.0)  # type: ignore[attr-defined]
        assert service.net_weight == pytest.approx(30.0)
    finally:
        service.close()


def test_device_mode_tare_and_zero_reset_offsets(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    dummy_writer = DummyTomliW()
    monkeypatch.setattr(scale, "tomli_w", dummy_writer)
    service = _make_service(monkeypatch, tmp_path, host_mode=False)
    try:
        service._process_sample(42.0)  # type: ignore[attr-defined]
        service.tare()
        assert service.calibration_offset == pytest.approx(0.0)
        assert service._tare == pytest.approx(0.0)  # type: ignore[attr-defined]

        service._process_sample(100.0)  # type: ignore[attr-defined]
        assert service.net_weight == pytest.approx(100.0)

        service.zero()
        assert service.calibration_offset == pytest.approx(0.0)
        assert service._tare == pytest.approx(0.0)  # type: ignore[attr-defined]
        assert dummy_writer.last_data is not None
        assert dummy_writer.last_data["offset"] == pytest.approx(0.0)
        assert dummy_writer.last_data["tare"] == pytest.approx(0.0)
        assert dummy_writer.last_data["mode"] == "device"

        service._process_sample(80.0)  # type: ignore[attr-defined]
        assert service.net_weight == pytest.approx(80.0)
    finally:
        service.close()

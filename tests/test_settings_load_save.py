"""Tests for robust configuration loading and saving."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bascula.config import settings as settings_mod
from bascula.config.settings import Settings


def _prepare_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BASCULA_SETTINGS_DIR", str(tmp_path))
    monkeypatch.setattr(settings_mod, "CONFIG_DIR", tmp_path, raising=False)
    monkeypatch.setattr(settings_mod, "CONFIG_PATH", tmp_path / "config.json", raising=False)
    monkeypatch.setattr(settings_mod, "BACKUP_PATH", tmp_path / "config.json.bak", raising=False)


def _load_with_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    _prepare_paths(tmp_path, monkeypatch)
    return Settings.load(settings_mod.CONFIG_PATH)


def test_load_missing_creates_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _load_with_tmp(tmp_path, monkeypatch)
    cfg_path = settings_mod.CONFIG_PATH
    assert cfg_path.exists()
    payload = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert payload["scale"]["port"] == "__dummy__"
    assert settings.scale.calib_factor == pytest.approx(1.0)


def test_load_empty_and_corrupt_recovers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text("", encoding="utf-8")
    settings = _load_with_tmp(tmp_path, monkeypatch)
    assert settings.scale.unit == "g"
    cfg_path.write_text("{invalid", encoding="utf-8")
    settings = _load_with_tmp(tmp_path, monkeypatch)
    assert settings.scale.decimals in (0, 1)


def test_save_atomic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _load_with_tmp(tmp_path, monkeypatch)
    settings.general.sound_enabled = False
    settings.scale.calibration_factor = 2.5
    settings.save(settings_mod.CONFIG_PATH)
    cfg_path = settings_mod.CONFIG_PATH
    tmp_file = cfg_path.with_suffix(".tmp")
    assert not tmp_file.exists()
    payload = json.loads(cfg_path.read_text(encoding="utf-8"))
    assert payload["general"]["sound_enabled"] is False
    assert payload["scale"]["calib_factor"] == pytest.approx(2.5)

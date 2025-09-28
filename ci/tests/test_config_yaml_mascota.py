"""Regression tests ensuring mascota toggle preserves config.yaml keys."""
from __future__ import annotations

import logging
from pathlib import Path

import yaml

from bascula.ui import app as app_module
from bascula.ui.app import BasculaApp


def _make_app(monkeypatch, tmp_path: Path, initial_config: dict) -> tuple[BasculaApp, Path]:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(initial_config, sort_keys=True, allow_unicode=True),
        encoding="utf-8",
    )
    lock_path = tmp_path / "bascula-config.lock"
    monkeypatch.setattr(app_module, "_CONFIG_PATH", config_path)
    monkeypatch.setattr(app_module, "_CONFIG_LOCK_PATH", lock_path)
    app = BasculaApp.__new__(BasculaApp)  # type: ignore[call-arg]
    app._mascota_enabled = False
    app._ui_cfg = {}
    app._config_yaml = {}
    app._save_ui_cfg = lambda: None  # type: ignore[assignment]
    app._update_mascota_visibility = lambda: None  # type: ignore[assignment]
    app.logger = logging.getLogger("test.mascota")
    return app, config_path


def test_set_mascota_enabled_preserves_other_keys(monkeypatch, tmp_path) -> None:
    initial = {
        "network": {"miniweb_pin": "123456"},
        "ui": {"theme": "holo"},
    }
    app, config_path = _make_app(monkeypatch, tmp_path, initial)
    app.set_mascota_enabled(True)
    on_disk = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert on_disk["network"]["miniweb_pin"] == "123456"
    assert on_disk["ui"]["theme"] == "holo"
    assert on_disk["ui"]["show_mascota"] is True
    assert app._config_yaml["ui"]["show_mascota"] is True


def test_set_mascota_disabled_keeps_existing_keys(monkeypatch, tmp_path) -> None:
    initial = {
        "network": {"miniweb_pin": "654321"},
        "ui": {"theme": "retro", "show_mascota": True},
    }
    app, config_path = _make_app(monkeypatch, tmp_path, initial)
    app._config_yaml = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    app.set_mascota_enabled(False)
    on_disk = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert on_disk["network"]["miniweb_pin"] == "654321"
    assert on_disk["ui"]["theme"] == "retro"
    assert on_disk["ui"]["show_mascota"] is False
    assert app._config_yaml["ui"]["show_mascota"] is False


def test_set_mascota_enabled_is_idempotent(monkeypatch, tmp_path) -> None:
    initial = {
        "network": {"miniweb_pin": "777777"},
        "ui": {"theme": "classic"},
    }
    app, config_path = _make_app(monkeypatch, tmp_path, initial)
    app.set_mascota_enabled(True)
    first = config_path.read_text(encoding="utf-8")
    app.set_mascota_enabled(True)
    second = config_path.read_text(encoding="utf-8")
    assert first == second

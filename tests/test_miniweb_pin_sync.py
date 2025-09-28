import yaml
import pytest

from bascula.config import pin as pin_module
from bascula.config.settings import Settings
from bascula.system.miniweb_pin import DEFAULT_FILE_MODE, sync_miniweb_pin


def test_ensure_pin_generates_and_persists(tmp_path):
    config_path = tmp_path / "config.yaml"

    pin, created = pin_module.ensure_miniweb_pin(
        config_path=config_path,
        pin_factory=lambda length: "123456",
    )

    assert created is True
    assert pin == "123456"
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert data["network"]["miniweb_pin"] == "123456"
    assert config_path.stat().st_mode & 0o777 == DEFAULT_FILE_MODE


def test_regenerate_pin_from_ui_calls_reload(tmp_path, monkeypatch):
    _ = pytest.importorskip("tkinter")
    from bascula.ui import app as app_module

    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump({"network": {"miniweb_pin": "111111"}}))

    monkeypatch.setenv("BASCULA_SETTINGS_DIR", str(tmp_path / "cfg"))
    monkeypatch.setattr(pin_module, "generate_pin", lambda length=6: "654321")

    reload_calls = []
    monkeypatch.setattr(app_module, "reload_miniweb_config", lambda: reload_calls.append(True) or True)

    settings = Settings()
    settings.network.miniweb_pin = "111111"

    class DummyVar:
        def __init__(self, value: str = "") -> None:
            self._value = value

        def set(self, value: str) -> None:
            self._value = value

        def get(self) -> str:
            return self._value

    app = object.__new__(app_module.BasculaApp)
    app._config_yaml_path = config_path
    app._miniweb_owner = None
    app._miniweb_group = None
    app.settings = settings
    app._miniweb_pin = "111111"
    app.miniweb_pin_var = DummyVar("111111")

    new_pin = app.regenerate_miniweb_pin()

    assert new_pin == "654321"
    assert app.miniweb_pin_var.get() == "654321"
    assert reload_calls, "Reload endpoint was not called"

    stored = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert stored["network"]["miniweb_pin"] == "654321"


def test_sync_miniweb_pin_updates_yaml(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    monkeypatch.setenv("BASCULA_SETTINGS_DIR", str(cfg_dir))

    settings = Settings()
    settings.network.miniweb_pin = "4444"

    config_yaml = tmp_path / "config.yaml"
    pin = sync_miniweb_pin(
        settings,
        config_path=config_yaml,
        owner=None,
        group=None,
        prefer_config=True,
    )

    assert pin.isdigit()
    assert 4 <= len(pin) <= 6
    data = yaml.safe_load(config_yaml.read_text(encoding="utf-8"))
    assert data["network"]["miniweb_pin"] == pin

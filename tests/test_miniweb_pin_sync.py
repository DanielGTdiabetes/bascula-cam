import json
from pathlib import Path

from bascula.config.settings import Settings
from bascula.system.miniweb_pin import DEFAULT_FILE_MODE, sync_miniweb_pin


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_sync_generates_pin_and_writes_files(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    cfg_path = cfg_dir / "config.json"
    auth_path = tmp_path / "auth.json"

    monkeypatch.setenv("BASCULA_SETTINGS_DIR", str(cfg_dir))

    settings = Settings()
    settings.network.miniweb_pin = ""

    pin = sync_miniweb_pin(
        settings,
        auth_path=auth_path,
        config_path=cfg_path,
        owner=None,
        group=None,
        prefer_config=True,
    )

    assert pin
    assert pin.isdigit()
    assert 4 <= len(pin) <= 6

    data = _load_json(cfg_path)
    assert data["network"]["miniweb_pin"] == pin

    payload = _load_json(auth_path)
    assert payload["pin"] == pin
    assert auth_path.stat().st_mode & 0o777 == DEFAULT_FILE_MODE


def test_sync_prefers_auth_when_not_forced(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    cfg_path = cfg_dir / "config.json"
    auth_path = tmp_path / "auth.json"

    monkeypatch.setenv("BASCULA_SETTINGS_DIR", str(cfg_dir))

    auth_path.write_text(json.dumps({"pin": "8888"}), encoding="utf-8")

    settings = Settings()
    settings.network.miniweb_pin = "4444"

    pin = sync_miniweb_pin(
        settings,
        auth_path=auth_path,
        config_path=cfg_path,
        owner=None,
        group=None,
        prefer_config=False,
    )

    assert pin == "8888"
    assert settings.network.miniweb_pin == "8888"
    data = _load_json(cfg_path)
    assert data["network"]["miniweb_pin"] == "8888"


def test_sync_prefers_config_when_requested(tmp_path, monkeypatch):
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    cfg_path = cfg_dir / "config.json"
    auth_path = tmp_path / "auth.json"

    monkeypatch.setenv("BASCULA_SETTINGS_DIR", str(cfg_dir))

    auth_path.write_text(json.dumps({"pin": "2222"}), encoding="utf-8")

    settings = Settings()
    settings.network.miniweb_pin = "7777"

    pin = sync_miniweb_pin(
        settings,
        auth_path=auth_path,
        config_path=cfg_path,
        owner=None,
        group=None,
        prefer_config=True,
    )

    assert pin == "7777"
    payload = _load_json(auth_path)
    assert payload["pin"] == "7777"

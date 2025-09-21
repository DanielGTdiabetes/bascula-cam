import importlib
import pathlib
import sys

import pytest


@pytest.fixture()
def miniweb(tmp_path, monkeypatch):
    """Load the mini-web module using a temporary config directory."""

    cfg_dir = tmp_path / "cfg"
    monkeypatch.setenv("BASCULA_CFG_DIR", str(cfg_dir))
    monkeypatch.setenv("BASCULA_MINIWEB_PORT", "8081")
    monkeypatch.setenv("BASCULA_WEB_HOST", "127.0.0.1")

    monkeypatch.setattr(pathlib.Path, "home", lambda: tmp_path)

    module_name = "bascula.services.wifi_config"
    if module_name in sys.modules:
        del sys.modules[module_name]

    module = importlib.import_module(module_name)
    module.app.config.update(TESTING=True)
    return module


@pytest.fixture()
def client(miniweb):
    client = miniweb.app.test_client()
    client.environ_base["REMOTE_ADDR"] = "127.0.0.1"
    return client


def test_health_endpoint_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"ok": True}


def test_status_requires_auth_without_local(monkeypatch, miniweb):
    client = miniweb.app.test_client()
    client.environ_base["REMOTE_ADDR"] = "198.51.100.10"
    response = client.get("/api/status")
    assert response.status_code == 401
    payload = response.get_json()
    assert payload["error"] == "auth"


def test_status_allows_local_requests(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload == {"ok": True, "api_key_present": False}


def test_apikey_roundtrip(client, miniweb):
    payload = {"key": "sk-test-12345678901234567890"}
    response = client.post("/api/apikey", json=payload)
    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert miniweb.API_FILE.exists()
    data = miniweb.API_FILE.read_text(encoding="utf-8")
    assert "sk-test-12345678901234567890" in data


def test_bolus_update_and_fetch(client, miniweb):
    update = {"tbg": 120, "isf": 45, "carb": 12, "dia": 5}
    resp = client.post("/api/bolus", json=update)
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True

    fetched = client.get("/api/bolus")
    assert fetched.status_code == 200
    data = fetched.get_json()
    assert data["ok"] is True
    assert data["data"]["tbg"] == 120
    assert data["data"]["isf"] == 45
    assert data["data"]["carb"] == 12
    assert data["data"]["dia"] == 5


def test_nightscout_store_and_load(client):
    payload = {"url": "https://ns.example.com", "token": "abc123"}
    resp = client.post("/api/nightscout", json=payload)
    assert resp.status_code == 200
    assert resp.get_json()["ok"] is True

    fetched = client.get("/api/nightscout")
    assert fetched.status_code == 200
    data = fetched.get_json()
    assert data["ok"] is True
    assert data["data"] == payload

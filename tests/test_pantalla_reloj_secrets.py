import json

import pytest
from fastapi.testclient import TestClient

from pantalla_reloj import create_app


@pytest.fixture()
def config_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("PANTALLA_RELOJ_CONFIG_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture()
def client(config_dir):
    app = create_app()
    return TestClient(app)


def test_config_schema_contains_secrets(client):
    response = client.get("/api/config/schema")
    payload = response.json()
    assert any(item["key"] == "aemet_api_key" for item in payload["secrets"])
    assert all(item["masked"] for item in payload["secrets"])


def test_save_secret_and_mask(client, config_dir):
    response = client.post("/api/config/secret/aemet_api_key", json={"value": "secret-key"})
    assert response.status_code == 200
    secrets_path = config_dir / "secrets.json"
    assert secrets_path.exists()
    data = json.loads(secrets_path.read_text(encoding="utf-8"))
    assert data["aemet_api_key"] == "secret-key"
    mode = secrets_path.stat().st_mode & 0o777
    assert mode == 0o600

    cfg = client.get("/api/config").json()
    assert cfg["secrets"]["aemet_api_key"] is True
    assert "secret-key" not in json.dumps(cfg)


def test_delete_secret(client, config_dir):
    client.post("/api/config/secret/aemet_api_key", json={"value": "abc"})
    response = client.delete("/api/config/secret/aemet_api_key")
    assert response.status_code == 200
    payload = json.loads((config_dir / "secrets.json").read_text(encoding="utf-8"))
    assert "aemet_api_key" not in payload


def test_blank_secret_removes_value(client, config_dir):
    client.post("/api/config/secret/aemet_api_key", json={"value": "abc"})
    client.post("/api/config/secret/aemet_api_key", json={"value": ""})
    payload = json.loads((config_dir / "secrets.json").read_text(encoding="utf-8"))
    assert "aemet_api_key" not in payload


class DummyAemetResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class DummyAemetClient:
    def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - initialization shim
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, headers=None):
        return DummyAemetResponse(status_code=200)


class DummyOpenSkyResponse:
    status_code = 200
    headers = {}

    def json(self):
        return {"access_token": "demo", "expires_in": 120, "scope": "test"}


class DummyOpenSkyClient:
    def __init__(self, *args, **kwargs) -> None:  # pragma: no cover - initialization shim
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, data=None, headers=None):
        return DummyOpenSkyResponse()


def test_aemet_test_endpoint(monkeypatch, client):
    monkeypatch.setattr("pantalla_reloj.integrations.aemet.httpx.AsyncClient", DummyAemetClient)
    client.post("/api/config/secret/aemet_api_key", json={"value": "key"})
    response = client.get("/api/aemet/test")
    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_opensky_test_endpoint(monkeypatch, client):
    monkeypatch.setattr("pantalla_reloj.integrations.opensky.httpx.AsyncClient", DummyOpenSkyClient)
    client.post("/api/config/secret/opensky_client_id", json={"value": "id"})
    client.post("/api/config/secret/opensky_client_secret", json={"value": "secret"})
    response = client.get("/api/opensky/test")
    assert response.status_code == 200
    data = response.json()
    assert data["token_valid"] is True
    assert data["expires_in"] >= 0


def test_health_endpoint(monkeypatch, client):
    monkeypatch.setattr("pantalla_reloj.integrations.aemet.httpx.AsyncClient", DummyAemetClient)
    monkeypatch.setattr("pantalla_reloj.integrations.opensky.httpx.AsyncClient", DummyOpenSkyClient)
    client.post("/api/config/secret/opensky_client_id", json={"value": "id"})
    client.post("/api/config/secret/opensky_client_secret", json={"value": "secret"})
    client.get("/api/aemet/test")
    client.get("/api/opensky/test")
    health = client.get("/api/health/full").json()
    assert "aemet" in health["integrations"]
    assert "token_set" in health["integrations"]["opensky"]
    assert health["secrets"]["opensky_client_id"] is True

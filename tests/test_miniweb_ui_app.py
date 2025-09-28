import importlib
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def miniweb_app(tmp_path, monkeypatch):
    monkeypatch.setenv("MINIWEB_PIN", "123456")
    import bascula.miniweb as miniweb_module

    miniweb = importlib.reload(miniweb_module)

    auth_state = tmp_path / "auth.json"
    monkeypatch.setattr(miniweb, "AUTH_STATE_DIR", tmp_path)
    monkeypatch.setattr(miniweb, "AUTH_STATE_FALLBACK_DIR", tmp_path)
    monkeypatch.setattr(miniweb, "AUTH_STATE_PATH", auth_state)
    monkeypatch.setattr(miniweb, "CONFIG_YAML_PATH", tmp_path / "config.yaml")
    monkeypatch.setattr(miniweb, "SECRETS_ENV_PATH", tmp_path / "secrets.env")

    miniweb.auth_manager = miniweb.AuthManager()
    app = miniweb.create_app()
    return app, miniweb


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_health_ok(miniweb_app):
    app, _ = miniweb_app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}


@pytest.mark.anyio
async def test_login_page_and_protection(miniweb_app):
    app, _ = miniweb_app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/")
        assert response.status_code in {302, 303}
        assert response.headers["location"].endswith("/login")

        login_page = await client.get("/login")
        assert login_page.status_code == 200
        assert "Introduce el PIN" in login_page.text


@pytest.mark.anyio
async def test_login_rate_limit(miniweb_app):
    app, _ = miniweb_app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        for _ in range(5):
            resp = await client.post("/login", data={"pin": "0000"})
            assert resp.status_code == 200
            assert "PIN incorrecto" in resp.text

        locked = await client.post("/login", data={"pin": "0000"})
        assert locked.status_code == 200
        assert "Intentos bloqueados" in locked.text


@pytest.mark.anyio
async def test_successful_login_and_home(miniweb_app):
    app, _ = miniweb_app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.post("/login", data={"pin": "123456"}, follow_redirects=False)
        assert resp.status_code == 303
        assert resp.headers["location"] == "/"

        home = await client.get("/")
        assert home.status_code == 200
        assert "Panel de control" in home.text


@pytest.mark.anyio
async def test_wifi_connect_form_flow(miniweb_app, monkeypatch):
    app, miniweb = miniweb_app

    def fake_run_command(args, **_kwargs):
        if args[:4] == ["nmcli", "dev", "wifi", "connect"]:
            return SimpleNamespace(stdout="")
        return SimpleNamespace(stdout="test")

    monkeypatch.setattr(miniweb, "run_command", fake_run_command)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        login = await client.post("/auth/login", json={"pin": "123456"})
        assert login.status_code == 200
        csrf_token = login.json()["csrf_token"]

        response = await client.post(
            "/config/wifi/connect",
            json={"ssid": "TestNet", "psk": "secret", "csrf_token": csrf_token},
            headers={"X-CSRF-Token": csrf_token},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["method"] == "nmcli"
    assert "Conexión solicitada" in payload["note"]


@pytest.mark.anyio
async def test_protected_api_without_cookie(miniweb_app):
    _, miniweb = miniweb_app
    app = miniweb.create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/ota/status")
    assert response.status_code == 401

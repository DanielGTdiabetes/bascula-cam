from fastapi.testclient import TestClient

from bascula.web.app import app


def test_web_root_returns_200():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "Bascula" in response.text

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app


def test_ios_origin_is_in_default_cors_settings(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    settings = Settings(_env_file=None)

    assert "http://localhost:5173" in settings.cors_origin_list
    assert "http://localhost:3000" in settings.cors_origin_list
    assert "capacitor://localhost" in settings.cors_origin_list


def test_ios_cors_preflight():
    response = TestClient(app).options(
        "/api/v1/teams",
        headers={
            "Origin": "capacitor://localhost",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "capacitor://localhost"
    )

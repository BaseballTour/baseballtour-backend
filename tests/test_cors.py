from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_cors_preflight_allows_local_frontend() -> None:
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )

    assert response.status_code == 200
    assert (
        response.headers["access-control-allow-origin"]
        == "http://localhost:5173"
    )
    assert (
        response.headers["access-control-allow-credentials"]
        == "true"
    )


def test_cors_rejects_unknown_origin() -> None:
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://not-allowed.example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_classifications_endpoint_is_not_public() -> None:
    response = client.get("/api/v1/tour/classifications")
    assert response.status_code == 404

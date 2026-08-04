from fastapi.testclient import TestClient

from app.api.v1.endpoints import tour as tour_endpoint
from app.core.exceptions import AppException
from app.main import app
from app.models.place import (
    Place,
    PlaceCategory,
    PlaceSource,
)


client = TestClient(app)


def make_place() -> Place:
    return Place(
        place_id="tour_123456",
        name="테스트 음식점",
        category=PlaceCategory.RESTAURANT,
        latitude=37.5122,
        longitude=127.0719,
        address="서울특별시 송파구",
        default_stay_minutes=60,
        source=PlaceSource.TOUR_API,
        source_content_id="123456",
        content_type_id="39",
    )


def test_nearby_returns_place_and_meta(
    monkeypatch,
) -> None:
    async def fake_get_nearby_place_list(
        **kwargs,
    ) -> list[Place]:
        return [make_place()]

    monkeypatch.setattr(
        tour_endpoint.tour_api_adapter,
        "get_nearby_place_list",
        fake_get_nearby_place_list,
    )

    response = client.get(
        "/api/v1/tour/nearby",
        params={
            "longitude": 127.0719,
            "latitude": 37.5122,
            "radius": 2000,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert body["meta"]["count"] == 1
    assert body["meta"]["nextPageToken"] is None

    [place] = body["data"]

    assert place["placeId"] == "tour_123456"
    assert place["category"] == "RESTAURANT"


def test_nearby_rejects_invalid_coordinate() -> None:
    response = client.get(
        "/api/v1/tour/nearby",
        params={
            "longitude": 127.0719,
            "latitude": 91,
            "radius": 2000,
        },
    )

    assert response.status_code == 422

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_nearby_propagates_tour_api_error(
    monkeypatch,
) -> None:
    async def fake_get_nearby_place_list(
        **kwargs,
    ) -> list[Place]:
        raise AppException(
            status_code=429,
            code="EXTERNAL_API_RATE_LIMITED",
            message="TourAPI 호출 제한을 초과했습니다.",
        )

    monkeypatch.setattr(
        tour_endpoint.tour_api_adapter,
        "get_nearby_place_list",
        fake_get_nearby_place_list,
    )

    response = client.get(
        "/api/v1/tour/nearby",
        params={
            "longitude": 127.0719,
            "latitude": 37.5122,
            "radius": 2000,
        },
    )

    assert response.status_code == 429

    body = response.json()

    assert body["success"] is False
    assert (
        body["error"]["code"]
        == "EXTERNAL_API_RATE_LIMITED"
    )

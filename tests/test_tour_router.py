from fastapi.testclient import TestClient

from app.api.v1.endpoints import tour as tour_endpoint
from app.core.exceptions import AppException
from app.external.tour_api.adapter import NearbyPlacePage
from app.main import app
from app.models.place import (
    Place,
    PlaceCategory,
    PlaceSource,
)
from app.schemas.player_pick import PlayerPickResponse


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
    received = {}

    async def fake_get_nearby_place_page(
        **kwargs,
    ) -> NearbyPlacePage:
        received.update(kwargs)
        return NearbyPlacePage(
            places=[make_place()],
            next_page_token="3",
        )

    monkeypatch.setattr(
        tour_endpoint.tour_api_adapter,
        "get_nearby_place_page",
        fake_get_nearby_place_page,
    )

    response = client.get(
        "/api/v1/tour/nearby",
        params={
            "longitude": 127.0719,
            "latitude": 37.5122,
            "radius": 2000,
            "category": "RESTAURANT",
            "pageSize": 10,
            "pageToken": "2",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert body["meta"]["count"] == 1
    assert body["meta"]["nextPageToken"] == "3"

    [place] = body["data"]

    assert place["placeId"] == "tour_123456"
    assert place["category"] == "RESTAURANT"

    assert received["page_no"] == 2
    assert received["num_of_rows"] == 10
    assert received["category"] == PlaceCategory.RESTAURANT


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


def test_nearby_rejects_invalid_page_token() -> None:
    response = client.get(
        "/api/v1/tour/nearby",
        params={
            "pageToken": "invalid",
        },
    )

    assert response.status_code == 400
    assert (
        response.json()["error"]["code"]
        == "INVALID_PAGE_TOKEN"
    )


def test_nearby_rejects_other_category() -> None:
    response = client.get(
        "/api/v1/tour/nearby",
        params={
            "category": "OTHER",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_nearby_propagates_tour_api_error(
    monkeypatch,
) -> None:
    async def fake_get_nearby_place_page(
        **kwargs,
    ) -> NearbyPlacePage:
        raise AppException(
            status_code=429,
            code="EXTERNAL_API_RATE_LIMITED",
            message="TourAPI 호출 제한을 초과했습니다.",
        )

    monkeypatch.setattr(
        tour_endpoint.tour_api_adapter,
        "get_nearby_place_page",
        fake_get_nearby_place_page,
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


def test_detail_requires_only_place_id(monkeypatch) -> None:
    received: dict[str, str] = {}

    async def fake_get_place_detail(content_id: str) -> Place:
        received["content_id"] = content_id
        return make_place()

    monkeypatch.setattr(
        tour_endpoint.tour_api_adapter,
        "get_place_detail",
        fake_get_place_detail,
    )

    response = client.get("/api/v1/tour/places/tour_123456")

    assert response.status_code == 200
    assert response.json()["data"]["placeId"] == "tour_123456"
    assert received["content_id"] == "123456"


def test_detail_rejects_raw_content_id() -> None:
    response = client.get("/api/v1/tour/places/123456")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PLACE_ID"


def test_player_picks_returns_db_curated_places(monkeypatch) -> None:
    received: dict[str, str | None] = {}

    class FakePlayerPickService:
        async def get_player_picks(
            self,
            *,
            stadium_id: str,
            player_name: str | None = None,
        ) -> list[PlayerPickResponse]:
            received["stadium_id"] = stadium_id
            received["player_name"] = player_name
            return [
                PlayerPickResponse(
                    player_pick_id="player_pick_001",
                    stadium_id=stadium_id,
                    player_name=player_name or "테스트 선수",
                    place=make_place(),
                )
            ]

    monkeypatch.setattr(
        tour_endpoint,
        "PlayerPickService",
        FakePlayerPickService,
    )

    response = client.get(
        "/api/v1/tour/player-picks",
        params={"stadiumId": "gocheok", "playerName": "테스트 선수"},
    )

    assert response.status_code == 200
    assert response.json()["data"][0]["place"]["placeId"] == "tour_123456"
    assert received == {
        "stadium_id": "gocheok",
        "player_name": "테스트 선수",
    }

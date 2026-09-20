from datetime import datetime
from zoneinfo import ZoneInfo

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
    assert received["category"] is None


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


def test_nearby_does_not_publish_legacy_category_parameter() -> None:
    operation = app.openapi()["paths"]["/api/v1/tour/nearby"]["get"]
    parameter_names = {
        parameter["name"] for parameter in operation["parameters"]
    }
    assert "category" not in parameter_names


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
        ) -> list[Place]:
            received["stadium_id"] = stadium_id
            received["player_name"] = player_name
            return [
                make_place().model_copy(update={
                    "place_id": "player_pick_001",
                    "is_player_pick": True,
                    "player_pick_id": "player_pick_001",
                    "stadium_id": stadium_id,
                    "recommended_by_players": [player_name or "테스트 선수"],
                    "recommended_by_player_positions": ["INFIELDER"],
                    "recommendation_note": "선수 부모님이 운영하는 가게",
                    "recommendation_evidence_status": "VERIFIED",
                    "recommendation_source_url": (
                        "https://www.youtube.com/watch?v=source"
                    ),
                    "recommendation_source_title": "선수 추천 맛집",
                    "recommendation_source_publisher": "구단 공식 채널",
                    "recommendation_verified_at": (
                        datetime(
                            2026,
                            9,
                            13,
                            12,
                            0,
                            tzinfo=ZoneInfo("Asia/Seoul"),
                        )
                    ),
                })
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
    assert response.json()["data"][0]["placeId"] == "player_pick_001"
    assert response.json()["data"][0]["recommendationNote"] == (
        "선수 부모님이 운영하는 가게"
    )
    assert response.json()["data"][0]["recommendedByPlayers"] == [
        "테스트 선수"
    ]
    assert response.json()["data"][0]["recommendedByPlayerPositions"] == [
        "INFIELDER"
    ]
    assert response.json()["data"][0]["recommendationSourceUrl"] == (
        "https://www.youtube.com/watch?v=source"
    )
    assert response.json()["data"][0]["recommendationEvidenceStatus"] == (
        "VERIFIED"
    )
    assert received == {
        "stadium_id": "gocheok",
        "player_name": "테스트 선수",
    }

from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_current_active_user_id
from app.core.exceptions import AppException
from app.main import app
from app.models.place import Place
from app.schemas.itinerary_plan import (
    ItineraryPlanRecord,
    ItineraryPlanStatus,
)


USER_ID = "firebase-user-123"
TRIP_ID = "trip_001"

CREATED_AT = datetime(
    2026,
    8,
    12,
    14,
    0,
    tzinfo=timezone.utc,
)


def make_plan() -> ItineraryPlanRecord:
    return ItineraryPlanRecord(
        plan_id="plan_001",
        trip_id=TRIP_ID,
        user_id=USER_ID,
        status=ItineraryPlanStatus.ACTIVE,
        algorithm_version="greedy-anchor-v0.1",
        total_travel_minutes=24,
        days=[
            {
                "date": "2026-08-15",
                "dayType": "GAME_DAY",
                "items": [
                    {
                        "itemId": "item_1_1",
                        "type": "STADIUM",
                        "sequence": 1,
                        "placeId": "sajik",
                        "name": "사직야구장",
                        "address": "부산광역시 동래구 사직로 45",
                        "latitude": 35.194,
                        "longitude": 129.0615,
                        "scheduledStartAt": (
                            "2026-08-15T17:20:00+09:00"
                        ),
                        "scheduledEndAt": (
                            "2026-08-15T21:00:00+09:00"
                        ),
                        "travelMinutesFromPrevious": 24,
                        "travelTimeSource": "ODSAY",
                        "isRequired": True,
                    }
                ],
            }
        ],
        excluded_places=[],
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


@pytest.fixture
def authenticated_client() -> TestClient:
    app.dependency_overrides[get_current_active_user_id] = (
        lambda: USER_ID
    )

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_create_itinerary_returns_created_plan(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.generate = AsyncMock(
        return_value=make_plan()
    )

    with patch(
        "app.api.v1.endpoints.trips.ItineraryGenerationService",
        return_value=service,
    ):
        response = authenticated_client.post(
            f"/api/v1/trips/{TRIP_ID}/itineraries"
        )

    assert response.status_code == 201

    body = response.json()

    assert body["success"] is True

    data = body["data"]

    assert data["planId"] == "plan_001"
    assert data["tripId"] == TRIP_ID
    assert data["status"] == "ACTIVE"
    assert data["algorithmVersion"] == (
        "greedy-anchor-v0.1"
    )
    assert data["totalTravelMinutes"] == 24

    item = data["days"][0]["items"][0]

    assert item["itemId"] == "item_1_1"
    assert item["type"] == "STADIUM"
    assert item["travelMinutesFromPrevious"] == 24
    assert item["travelTimeSource"] == "ODSAY"

    assert data["excludedPlaces"] == []

    # 저장 전용 메타데이터는 API 응답에서 노출하지 않습니다.
    assert "userId" not in data
    assert "createdAt" not in data
    assert "updatedAt" not in data

    service.generate.assert_awaited_once_with(
        user_id=USER_ID,
        trip_id=TRIP_ID,
    )


def test_recommendation_candidates_preserve_external_timeout_response(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.get_recommendation_candidates = AsyncMock(
        side_effect=AppException(
            status_code=503,
            code="EXTERNAL_API_TIMEOUT",
            message="TourAPI 요청 시간이 초과되었습니다.",
            details={
                "endpoint": "locationBasedList2",
                "timeoutType": "ReadTimeout",
                "attempts": 2,
                "elapsedMs": 20250,
            },
        )
    )

    with patch(
        "app.api.v1.endpoints.trips.ItineraryGenerationService",
        return_value=service,
    ):
        response = authenticated_client.get(
            f"/api/v1/trips/{TRIP_ID}/recommendation-candidates"
        )

    assert response.status_code == 503
    assert response.json() == {
        "success": False,
        "error": {
            "code": "EXTERNAL_API_TIMEOUT",
            "message": "TourAPI 요청 시간이 초과되었습니다.",
            "details": [{
                "endpoint": "locationBasedList2",
                "timeoutType": "ReadTimeout",
                "attempts": 2,
                "elapsedMs": 20250,
            }],
        },
    }


def _candidate(
    place_id: str,
    name: str,
    *,
    category: str = "RESTAURANT",
    distance: float = 100,
    lcls2: str | None = "FD01",
    player_pick: bool = False,
) -> Place:
    return Place(
        placeId=place_id,
        name=name,
        category=category,
        latitude=37.5,
        longitude=127.0,
        address="서울특별시",
        distanceMeters=distance,
        source="LOCAL_DATA" if player_pick else "TOUR_API",
        sourceContentId=None if player_pick else place_id.removeprefix("tour_"),
        lclsSystem1="FD",
        lclsSystem2=lcls2,
        isPlayerPick=player_pick,
    )


def test_recommendation_candidates_filter_sort_and_paginate(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.get_recommendation_candidates = AsyncMock(
        return_value=[
            _candidate("tour_1", "먼 한식", distance=300),
            _candidate("tour_2", "가까운 한식", distance=50),
            _candidate("tour_3", "다른 음식", lcls2="FD02", distance=10),
        ]
    )
    with patch(
        "app.api.v1.endpoints.trips.ItineraryGenerationService",
        return_value=service,
    ):
        response = authenticated_client.get(
            f"/api/v1/trips/{TRIP_ID}/recommendation-candidates"
            "?filterId=KOREAN&keyword=한식&sort=DISTANCE&pageSize=1"
        )

    assert response.status_code == 200
    assert response.json()["data"][0]["placeId"] == "tour_2"
    assert response.json()["meta"] == {"count": 1, "nextPageToken": "2"}


def test_recommendation_candidates_support_player_pick_filter(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.get_recommendation_candidates = AsyncMock(
        return_value=[
            _candidate("tour_1", "일반 장소"),
            _candidate("player_place_1", "선수 추천", player_pick=True),
        ]
    )
    with patch(
        "app.api.v1.endpoints.trips.ItineraryGenerationService",
        return_value=service,
    ):
        response = authenticated_client.get(
            f"/api/v1/trips/{TRIP_ID}/recommendation-candidates"
            "?filterId=PLAYER_PICK"
        )

    assert response.status_code == 200
    assert [item["placeId"] for item in response.json()["data"]] == [
        "player_place_1"
    ]


def test_recommendation_candidates_reject_invalid_page_token(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.get_recommendation_candidates = AsyncMock(return_value=[])
    with patch(
        "app.api.v1.endpoints.trips.ItineraryGenerationService",
        return_value=service,
    ):
        response = authenticated_client.get(
            f"/api/v1/trips/{TRIP_ID}/recommendation-candidates"
            "?pageToken=bad"
        )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PAGE_TOKEN"


def test_create_itinerary_has_no_request_body(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.generate = AsyncMock(
        return_value=make_plan()
    )

    with patch(
        "app.api.v1.endpoints.trips.ItineraryGenerationService",
        return_value=service,
    ):
        response = authenticated_client.post(
            f"/api/v1/trips/{TRIP_ID}/itineraries"
        )

    assert response.status_code == 201
    service.generate.assert_awaited_once()


def test_regenerate_itinerary_day_passes_target_date(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.generate = AsyncMock(return_value=make_plan())
    with patch(
        "app.api.v1.endpoints.trips.ItineraryGenerationService",
        return_value=service,
    ):
        response = authenticated_client.post(
            f"/api/v1/trips/{TRIP_ID}/plan/days/2026-08-15/regenerate"
        )

    assert response.status_code == 200
    service.generate.assert_awaited_once_with(
        user_id=USER_ID,
        trip_id=TRIP_ID,
        target_date=datetime(2026, 8, 15).date(),
    )


def test_create_itinerary_requires_authentication() -> None:
    app.dependency_overrides.clear()

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/trips/{TRIP_ID}/itineraries"
        )

    assert response.status_code == 401

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "AUTH_TOKEN_MISSING"

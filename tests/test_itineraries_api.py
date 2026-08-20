from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_current_active_user_id
from app.main import app
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

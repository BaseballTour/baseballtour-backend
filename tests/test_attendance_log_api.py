from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import (
    get_current_active_user_id,
)
from app.main import app
from app.schemas.itinerary_plan import (
    ItineraryPlanRecord,
    ItineraryPlanStatus,
)


USER_ID = "firebase-user-123"
TRIP_ID = "trip_001"
PLAN_ID = "plan_001"
ATTENDANCE_LOG_ID = "log_001"

NOW = datetime(
    2026,
    8,
    19,
    3,
    0,
    tzinfo=timezone.utc,
)


def make_plan() -> ItineraryPlanRecord:
    return ItineraryPlanRecord(
        plan_id=PLAN_ID,
        trip_id=TRIP_ID,
        user_id=USER_ID,
        status=ItineraryPlanStatus.ARCHIVED,
        algorithm_version="auto-fill-v0.4",
        total_travel_minutes=15,
        total_travel_distance_meters=1200,
        days=[
            {
                "date": "2026-08-15",
                "dayType": "GAME_DAY",
                "items": [
                    {
                        "itemId": "place_1",
                        "type": "PLACE",
                        "sequence": 1,
                        "placeId": "tour_001",
                        "category": "TOURIST_SPOT",
                        "thumbnailUrl": (
                            "https:"
                            "//example.com/gwangalli.jpg"
                        ),
                        "shortDescription": (
                            "부산을 대표하는 해변 관광지"
                        ),
                        "overview": (
                            "부산을 대표하는 해변 관광지입니다."
                        ),
                        "name": "광안리해수욕장",
                        "address": "부산광역시 수영구",
                        "latitude": 35.1532,
                        "longitude": 129.1187,
                        "scheduledStartAt": (
                            "2026-08-15T14:00:00+09:00"
                        ),
                        "scheduledEndAt": (
                            "2026-08-15T15:30:00+09:00"
                        ),
                        "travelMinutesFromPrevious": 15,
                        "travelDistanceMetersFromPrevious": 1200,
                        "travelMode": "TRANSIT",
                        "travelTimeSource": "KAKAO",
                        "isRequired": True,
                        "addedBy": "USER",
                    }
                ],
            }
        ],
        excluded_places=[],
        recommendation_summary=None,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.fixture
def authenticated_client() -> TestClient:
    app.dependency_overrides[
        get_current_active_user_id
    ] = lambda: USER_ID

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_get_attendance_log_itinerary_returns_saved_plan(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.get_itinerary.return_value = make_plan()

    with patch(
        (
            "app.api.v1.endpoints.attendance_logs."
            "AttendanceLogService"
        ),
        return_value=service,
    ):
        response = authenticated_client.get(
            (
                "/api/v1/attendance-logs/"
                f"{ATTENDANCE_LOG_ID}/itinerary"
            )
        )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True

    data = body["data"]

    assert data["planId"] == PLAN_ID
    assert data["tripId"] == TRIP_ID
    assert data["status"] == "ARCHIVED"
    assert data["algorithmVersion"] == "auto-fill-v0.4"
    assert data["totalTravelMinutes"] == 15
    assert data["totalTravelDistanceMeters"] == 1200

    item = data["days"][0]["items"][0]

    assert item["placeId"] == "tour_001"
    assert (
        item["thumbnailUrl"]
        == "https://example.com/gwangalli.jpg"
    )
    assert (
        item["shortDescription"]
        == "부산을 대표하는 해변 관광지"
    )
    assert (
        item["overview"]
        == "부산을 대표하는 해변 관광지입니다."
    )
    assert item["travelTimeSource"] == "KAKAO"

    assert "userId" not in data
    assert "createdAt" not in data
    assert "updatedAt" not in data

    service.get_itinerary.assert_called_once_with(
        user_id=USER_ID,
        attendance_log_id=ATTENDANCE_LOG_ID,
    )


def test_attendance_log_itinerary_is_get_only() -> None:
    target = (
        "/api/v1/attendance-logs/"
        "{attendanceLogId}/itinerary"
    )

    methods = {
        method.lower()
        for method in app.openapi()["paths"][target]
        if method.lower()
        in {
            "get",
            "post",
            "put",
            "patch",
            "delete",
            "options",
            "head",
        }
    }

    assert methods == {"get"}

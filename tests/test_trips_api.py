from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import (
    get_current_active_user_id,
)
from app.main import app
from app.schemas.trip import (
    AccommodationInfo,
    TripPoint,
    TripRecord,
)


USER_ID = "firebase-user-123"
TRIP_ID = "trip_auto_001"
GAME_ID = "dev_game_20260815_lotte_doosan"

TRIP_START_AT = datetime(
    2026,
    8,
    14,
    1,
    30,
    tzinfo=timezone.utc,
)
TRIP_END_AT = datetime(
    2026,
    8,
    16,
    10,
    0,
    tzinfo=timezone.utc,
)
CREATED_AT = datetime(
    2026,
    8,
    2,
    13,
    0,
    tzinfo=timezone.utc,
)
UPDATED_AT = datetime(
    2026,
    8,
    2,
    14,
    0,
    tzinfo=timezone.utc,
)


def make_trip_record(
    *,
    title: str = "두산 부산 원정",
) -> TripRecord:
    return TripRecord(
        trip_id=TRIP_ID,
        user_id=USER_ID,
        game_id=GAME_ID,
        title=title,
        trip_start_at=TRIP_START_AT,
        trip_end_at=TRIP_END_AT,
        arrival_point=TripPoint(
            name="부산역",
            latitude=35.1151,
            longitude=129.0414,
        ),
        departure_point=TripPoint(
            name="부산역",
            latitude=35.1151,
            longitude=129.0414,
        ),
        accommodation=AccommodationInfo(
            accommodation_id="accommodation_kakao_123456789",
            name="서면 숙소",
            address="부산광역시 부산진구",
            latitude=35.1577,
            longitude=129.0592,
        ),
        status="PLANNING",
        active_plan_id=None,
        created_at=CREATED_AT,
        updated_at=UPDATED_AT,
    )


def make_create_body() -> dict:
    return {
        "gameId": GAME_ID,
        "title": "두산 부산 원정",
        "tripStartAt": "2026-08-14T10:30:00+09:00",
        "tripEndAt": "2026-08-16T19:00:00+09:00",
        "arrivalPoint": {
            "name": "부산역",
            "latitude": 35.1151,
            "longitude": 129.0414,
        },
        "departurePoint": {
            "name": "부산역",
            "latitude": 35.1151,
            "longitude": 129.0414,
        },
        "accommodation": {
            "accommodationId": "accommodation_kakao_123456789",
            "kakaoPlaceId": "123456789",
            "name": "서면 숙소",
            "address": "부산광역시 부산진구",
            "latitude": 35.1577,
            "longitude": 129.0592,
        },
    }


@pytest.fixture
def authenticated_client() -> TestClient:
    app.dependency_overrides[get_current_active_user_id] = (
        lambda: USER_ID
    )

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_create_trip_returns_created_summary(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.create_trip.return_value = make_trip_record()

    with patch(
        "app.api.v1.endpoints.trips.TripService",
        return_value=service,
    ):
        response = authenticated_client.post(
            "/api/v1/trips",
            json=make_create_body(),
            headers={
                "Idempotency-Key": "trip-create-request-001",
            },
        )

    assert response.status_code == 201

    body = response.json()

    assert body["success"] is True
    assert body["data"] == {
        "tripId": TRIP_ID,
        "gameId": GAME_ID,
        "title": "두산 부산 원정",
        "status": "PLANNING",
        "tripStartAt": "2026-08-14T10:30:00+09:00",
        "tripEndAt": "2026-08-16T19:00:00+09:00",
        "createdAt": "2026-08-02T22:00:00+09:00",
    }
    assert "userId" not in body["data"]

    service.create_trip.assert_called_once()

    arguments = service.create_trip.call_args.kwargs

    assert arguments["user_id"] == USER_ID
    assert arguments["request"].game_id == GAME_ID
    assert arguments["request"].trip_start_at.isoformat() == (
        "2026-08-14T10:30:00+09:00"
    )
    assert arguments["request"].trip_end_at.isoformat() == (
        "2026-08-16T19:00:00+09:00"
    )
    assert arguments["request"].arrival_point.name == "부산역"
    assert arguments["request"].departure_point.name == "부산역"
    assert arguments["request"].accommodation.kakao_place_id == (
        "123456789"
    )
    assert arguments["request"].accommodation.accommodation_id == (
        "accommodation_kakao_123456789"
    )
    assert (
        arguments["idempotency_key"]
        == "trip-create-request-001"
    )


def test_create_trip_returns_accommodation_specific_validation_error(
    authenticated_client: TestClient,
) -> None:
    body = make_create_body()
    body["accommodation"]["accommodationId"] = "123456789"

    response = authenticated_client.post(
        "/api/v1/trips",
        json=body,
        headers={"Idempotency-Key": "invalid-accommodation-id"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ACCOMMODATION_INVALID"
    assert response.json()["error"]["message"] == (
        "숙소 정보를 확인해 주세요."
    )


def test_get_my_trips_returns_list_response(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.get_my_trips.return_value = [
        make_trip_record()
    ]

    with patch(
        "app.api.v1.endpoints.trips.TripService",
        return_value=service,
    ):
        response = authenticated_client.get(
            "/api/v1/trips"
        )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert len(body["data"]) == 1
    assert body["data"][0]["tripId"] == TRIP_ID
    assert body["meta"] == {
        "count": 1,
        "nextPageToken": None,
    }

    service.get_my_trips.assert_called_once_with(
        user_id=USER_ID,
    )


def test_get_my_trips_returns_empty_list(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.get_my_trips.return_value = []

    with patch(
        "app.api.v1.endpoints.trips.TripService",
        return_value=service,
    ):
        response = authenticated_client.get("/api/v1/trips")

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": [],
        "meta": {"count": 0, "nextPageToken": None},
    }


def test_get_trip_returns_detail(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.get_trip.return_value = make_trip_record()

    with patch(
        "app.api.v1.endpoints.trips.TripService",
        return_value=service,
    ):
        response = authenticated_client.get(
            f"/api/v1/trips/{TRIP_ID}"
        )

    assert response.status_code == 200

    data = response.json()["data"]

    assert data["tripId"] == TRIP_ID
    assert data["arrivalPoint"]["name"] == "부산역"
    assert data["departurePoint"]["name"] == "부산역"
    assert data["accommodation"]["name"] == "서면 숙소"
    assert data["accommodation"]["accommodationId"] == (
        "accommodation_kakao_123456789"
    )
    assert data["activePlanId"] is None
    assert "updatedAt" in data
    assert "userId" not in data

    service.get_trip.assert_called_once_with(
        user_id=USER_ID,
        trip_id=TRIP_ID,
    )


def test_update_trip_returns_updated_detail(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.update_trip.return_value = make_trip_record(
        title="수정된 부산 원정"
    )

    with patch(
        "app.api.v1.endpoints.trips.TripService",
        return_value=service,
    ):
        response = authenticated_client.patch(
            f"/api/v1/trips/{TRIP_ID}",
            json={
                "title": "수정된 부산 원정",
                "accommodation": None,
            },
        )

    assert response.status_code == 200
    assert (
        response.json()["data"]["title"]
        == "수정된 부산 원정"
    )

    service.update_trip.assert_called_once()

    arguments = service.update_trip.call_args.kwargs

    assert arguments["user_id"] == USER_ID
    assert arguments["trip_id"] == TRIP_ID
    assert arguments["request"].title == "수정된 부산 원정"
    assert arguments["request"].accommodation is None


def test_delete_trip_returns_no_content(
    authenticated_client: TestClient,
) -> None:
    service = Mock()

    with patch(
        "app.api.v1.endpoints.trips.TripService",
        return_value=service,
    ):
        response = authenticated_client.delete(
            f"/api/v1/trips/{TRIP_ID}"
        )

    assert response.status_code == 204
    assert response.content == b""

    service.delete_trip.assert_called_once_with(
        user_id=USER_ID,
        trip_id=TRIP_ID,
    )


def test_trips_api_requires_authentication() -> None:
    app.dependency_overrides.clear()

    with TestClient(app) as client:
        response = client.get("/api/v1/trips")

    assert response.status_code == 401

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "AUTH_TOKEN_MISSING"


def test_create_trip_requires_idempotency_key(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.post(
        "/api/v1/trips",
        json=make_create_body(),
    )

    assert response.status_code == 422
    assert (
        response.json()["error"]["code"]
        == "VALIDATION_ERROR"
    )

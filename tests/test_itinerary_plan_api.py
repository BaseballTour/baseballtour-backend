from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_current_user_id
from app.main import app
from app.schemas.itinerary_plan import (
    ItineraryPlanRecord,
    ItineraryPlanStatus,
)


USER_ID = "firebase-user-123"
TRIP_ID = "trip_001"
PLAN_ID = "plan_001"

NOW = datetime(
    2026,
    8,
    12,
    14,
    0,
    tzinfo=timezone.utc,
)


def make_plan() -> ItineraryPlanRecord:
    return ItineraryPlanRecord(
        plan_id=PLAN_ID,
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
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.fixture
def authenticated_client() -> TestClient:
    app.dependency_overrides[get_current_user_id] = (
        lambda: USER_ID
    )

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_get_active_itinerary_plan_returns_plan(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.get_active_plan.return_value = make_plan()

    with patch(
        "app.api.v1.endpoints.trips.ItineraryPlanService",
        return_value=service,
    ):
        response = authenticated_client.get(
            f"/api/v1/trips/{TRIP_ID}/plan"
        )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True

    data = body["data"]

    assert data["planId"] == PLAN_ID
    assert data["tripId"] == TRIP_ID
    assert data["status"] == "ACTIVE"
    assert data["algorithmVersion"] == (
        "greedy-anchor-v0.1"
    )
    assert data["totalTravelMinutes"] == 24

    item = data["days"][0]["items"][0]

    assert item["itemId"] == "item_1_1"
    assert item["travelTimeSource"] == "ODSAY"

    assert "userId" not in data
    assert "createdAt" not in data
    assert "updatedAt" not in data

    service.get_active_plan.assert_called_once_with(
        user_id=USER_ID,
        trip_id=TRIP_ID,
    )


def test_delete_active_itinerary_plan_returns_no_content(
    authenticated_client: TestClient,
) -> None:
    service = Mock()

    with patch(
        "app.api.v1.endpoints.trips.ItineraryPlanService",
        return_value=service,
    ):
        response = authenticated_client.delete(
            f"/api/v1/trips/{TRIP_ID}/plan"
        )

    assert response.status_code == 204
    assert response.content == b""

    service.delete_active_plan.assert_called_once_with(
        user_id=USER_ID,
        trip_id=TRIP_ID,
    )


def test_get_active_itinerary_plan_requires_authentication() -> None:
    app.dependency_overrides.clear()

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/trips/{TRIP_ID}/plan"
        )

    assert response.status_code == 401

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "AUTH_TOKEN_MISSING"


def test_delete_active_itinerary_plan_requires_authentication() -> None:
    app.dependency_overrides.clear()

    with TestClient(app) as client:
        response = client.delete(
            f"/api/v1/trips/{TRIP_ID}/plan"
        )

    assert response.status_code == 401

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "AUTH_TOKEN_MISSING"


def test_reorder_itinerary_items_returns_updated_plan(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.reorder_items = AsyncMock(
        return_value=make_plan()
    )

    with patch(
        "app.api.v1.endpoints.trips.ItineraryPlanService",
        return_value=service,
    ):
        response = authenticated_client.patch(
            f"/api/v1/trips/{TRIP_ID}/plan/items/order",
            json={
                "date": "2026-08-15",
                "itemIds": [
                    "item_1_2",
                    "item_1_1",
                ],
            },
        )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert body["data"]["planId"] == PLAN_ID

    service.reorder_items.assert_awaited_once()

    arguments = service.reorder_items.call_args.kwargs

    assert arguments["user_id"] == USER_ID
    assert arguments["trip_id"] == TRIP_ID

    request = arguments["request"]

    assert request.date.isoformat() == "2026-08-15"
    assert request.item_ids == [
        "item_1_2",
        "item_1_1",
    ]


def test_reorder_itinerary_items_rejects_duplicate_ids(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.patch(
        f"/api/v1/trips/{TRIP_ID}/plan/items/order",
        json={
            "date": "2026-08-15",
            "itemIds": [
                "item_1_1",
                "item_1_1",
            ],
        },
    )

    assert response.status_code == 422

    body = response.json()

    assert body["success"] is False


def test_reorder_itinerary_items_requires_authentication() -> None:
    app.dependency_overrides.clear()

    with TestClient(app) as client:
        response = client.patch(
            f"/api/v1/trips/{TRIP_ID}/plan/items/order",
            json={
                "date": "2026-08-15",
                "itemIds": [
                    "item_1_2",
                    "item_1_1",
                ],
            },
        )

    assert response.status_code == 401

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "AUTH_TOKEN_MISSING"


def test_delete_itinerary_item_returns_updated_plan(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.delete_item = AsyncMock(
        return_value=make_plan()
    )

    with patch(
        "app.api.v1.endpoints.trips.ItineraryPlanService",
        return_value=service,
    ):
        response = authenticated_client.delete(
            f"/api/v1/trips/{TRIP_ID}/plan/items/item_1_1"
        )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert body["data"]["planId"] == PLAN_ID

    service.delete_item.assert_awaited_once_with(
        user_id=USER_ID,
        trip_id=TRIP_ID,
        item_id="item_1_1",
    )


def test_delete_itinerary_item_passes_item_id(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.delete_item = AsyncMock(
        return_value=make_plan()
    )

    with patch(
        "app.api.v1.endpoints.trips.ItineraryPlanService",
        return_value=service,
    ):
        response = authenticated_client.delete(
            f"/api/v1/trips/{TRIP_ID}/plan/items/custom_item"
        )

    assert response.status_code == 200

    arguments = service.delete_item.call_args.kwargs

    assert arguments["trip_id"] == TRIP_ID
    assert arguments["item_id"] == "custom_item"


def test_delete_itinerary_item_requires_authentication() -> None:
    app.dependency_overrides.clear()

    with TestClient(app) as client:
        response = client.delete(
            f"/api/v1/trips/{TRIP_ID}/plan/items/item_1_1"
        )

    assert response.status_code == 401

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "AUTH_TOKEN_MISSING"


def test_add_itinerary_item_returns_updated_plan(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.add_item = AsyncMock(
        return_value=make_plan()
    )

    with patch(
        "app.api.v1.endpoints.trips.ItineraryPlanService",
        return_value=service,
    ):
        response = authenticated_client.post(
            f"/api/v1/trips/{TRIP_ID}/plan/items",
            json={
                "date": "2026-08-15",
                "placeId": "tour_123456",
                "isRequired": True,
            },
        )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert body["data"]["planId"] == PLAN_ID

    service.add_item.assert_awaited_once()

    arguments = service.add_item.call_args.kwargs

    assert arguments["user_id"] == USER_ID
    assert arguments["trip_id"] == TRIP_ID

    request = arguments["request"]

    assert request.date.isoformat() == "2026-08-15"
    assert request.place_id == "tour_123456"
    assert request.is_required is True


def test_add_itinerary_item_defaults_to_required(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.add_item = AsyncMock(
        return_value=make_plan()
    )

    with patch(
        "app.api.v1.endpoints.trips.ItineraryPlanService",
        return_value=service,
    ):
        response = authenticated_client.post(
            f"/api/v1/trips/{TRIP_ID}/plan/items",
            json={
                "date": "2026-08-15",
                "placeId": "tour_123456",
            },
        )

    assert response.status_code == 200

    request = service.add_item.call_args.kwargs[
        "request"
    ]

    assert request.is_required is True


def test_add_itinerary_item_requires_authentication() -> None:
    app.dependency_overrides.clear()

    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/trips/{TRIP_ID}/plan/items",
            json={
                "date": "2026-08-15",
                "placeId": "tour_123456",
                "isRequired": True,
            },
        )

    assert response.status_code == 401

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "AUTH_TOKEN_MISSING"

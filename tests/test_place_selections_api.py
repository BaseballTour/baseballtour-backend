from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import get_current_user_id
from app.main import app
from app.schemas.place_selection import PlaceSelectionRecord


USER_ID = "firebase-user-123"
TRIP_ID = "trip_auto_001"
PLACE_ID = "tour_123456"

CREATED_AT = datetime(
    2026,
    8,
    12,
    10,
    0,
    tzinfo=timezone.utc,
)


def make_selection(
    *,
    place_id: str = PLACE_ID,
    is_required: bool = True,
) -> PlaceSelectionRecord:
    return PlaceSelectionRecord(
        place_id=place_id,
        is_required=is_required,
        created_at=CREATED_AT,
    )


@pytest.fixture
def authenticated_client() -> TestClient:
    app.dependency_overrides[get_current_user_id] = (
        lambda: USER_ID
    )

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_create_place_selection_returns_created(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.create_selection.return_value = (
        make_selection()
    )

    with patch(
        "app.api.v1.endpoints.trips.PlaceSelectionService",
        return_value=service,
    ):
        response = authenticated_client.post(
            f"/api/v1/trips/{TRIP_ID}/place-selections",
            json={
                "placeId": PLACE_ID,
                "isRequired": True,
            },
        )

    assert response.status_code == 201

    body = response.json()

    assert body["success"] is True
    assert body["data"] == {
        "placeId": PLACE_ID,
        "isRequired": True,
        "createdAt": "2026-08-12T10:00:00Z",
    }

    service.create_selection.assert_called_once()

    arguments = service.create_selection.call_args.kwargs

    assert arguments["user_id"] == USER_ID
    assert arguments["trip_id"] == TRIP_ID
    assert arguments["request"].place_id == PLACE_ID
    assert arguments["request"].is_required is True


def test_get_place_selections_returns_list(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.get_selections.return_value = [
        make_selection(
            place_id="tour_001",
            is_required=True,
        ),
        make_selection(
            place_id="tour_002",
            is_required=False,
        ),
    ]

    with patch(
        "app.api.v1.endpoints.trips.PlaceSelectionService",
        return_value=service,
    ):
        response = authenticated_client.get(
            f"/api/v1/trips/{TRIP_ID}/place-selections"
        )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert len(body["data"]) == 2
    assert body["data"][0]["placeId"] == "tour_001"
    assert body["data"][0]["isRequired"] is True
    assert body["data"][1]["placeId"] == "tour_002"

    assert body["meta"] == {
        "count": 2,
        "nextPageToken": None,
    }

    service.get_selections.assert_called_once_with(
        user_id=USER_ID,
        trip_id=TRIP_ID,
    )


def test_delete_place_selection_returns_no_content(
    authenticated_client: TestClient,
) -> None:
    service = Mock()

    with patch(
        "app.api.v1.endpoints.trips.PlaceSelectionService",
        return_value=service,
    ):
        response = authenticated_client.delete(
            (
                f"/api/v1/trips/{TRIP_ID}"
                f"/place-selections/{PLACE_ID}"
            )
        )

    assert response.status_code == 204
    assert response.content == b""

    service.delete_selection.assert_called_once_with(
        user_id=USER_ID,
        trip_id=TRIP_ID,
        place_id=PLACE_ID,
    )


def test_place_selections_require_authentication() -> None:
    app.dependency_overrides.clear()

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/trips/{TRIP_ID}/place-selections"
        )

    assert response.status_code == 401

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "AUTH_TOKEN_MISSING"

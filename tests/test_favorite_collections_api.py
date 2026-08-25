from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import (
    get_current_active_user_id,
)
from app.main import app
from app.schemas.favorite_collection import (
    FavoriteCollectionItemDocument,
    FavoriteCollectionRecord,
)


USER_ID = "firebase-user-123"
COLLECTION_ID = "collection_001"

FIXED_TIME = datetime(
    2026,
    8,
    20,
    10,
    0,
    tzinfo=timezone.utc,
)


def make_collection(
    *,
    collection_id: str = COLLECTION_ID,
    name: str = "가보고 싶은 장소",
) -> FavoriteCollectionRecord:
    return FavoriteCollectionRecord(
        collection_id=collection_id,
        name=name,
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
    )


@pytest.fixture
def authenticated_client() -> TestClient:
    app.dependency_overrides[
        get_current_active_user_id
    ] = lambda: USER_ID

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_create_favorite_collection_returns_created(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.create_collection.return_value = (
        make_collection()
    )

    with patch(
        (
            "app.api.v1.endpoints.favorite_collections."
            "FavoriteCollectionService"
        ),
        return_value=service,
    ):
        response = authenticated_client.post(
            "/api/v1/users/me/favorite-collections",
            json={
                "name": "가보고 싶은 장소",
            },
        )

    assert response.status_code == 201

    body = response.json()

    assert body["success"] is True
    assert body["data"] == {
        "collectionId": COLLECTION_ID,
        "name": "가보고 싶은 장소",
        "thumbnailUrl": None,
        "createdAt": "2026-08-20T19:00:00+09:00",
        "updatedAt": "2026-08-20T19:00:00+09:00",
    }

    arguments = (
        service.create_collection.call_args.kwargs
    )

    assert arguments["user_id"] == USER_ID
    assert arguments["request"].name == "가보고 싶은 장소"


def test_get_favorite_collections_returns_list(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.get_collections.return_value = [
        make_collection(
            collection_id="collection_001",
            name="맛집",
        ),
        make_collection(
            collection_id="collection_002",
            name="관광지",
        ),
    ]
    service.get_collection_thumbnails = AsyncMock(
        return_value={
            "collection_001": "https://example.com/food.jpg",
            "collection_002": None,
        }
    )

    with patch(
        (
            "app.api.v1.endpoints.favorite_collections."
            "FavoriteCollectionService"
        ),
        return_value=service,
    ):
        response = authenticated_client.get(
            "/api/v1/users/me/favorite-collections"
        )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert len(body["data"]) == 2
    assert body["data"][0]["name"] == "맛집"
    assert body["data"][0]["thumbnailUrl"] == "https://example.com/food.jpg"
    assert body["data"][1]["name"] == "관광지"

    assert body["meta"] == {
        "count": 2,
        "nextPageToken": None,
    }

    service.get_collections.assert_called_once_with(
        user_id=USER_ID
    )


def test_get_favorite_collection_places_returns_places(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.get_collection_places = AsyncMock(return_value=[])
    with patch(
        "app.api.v1.endpoints.favorite_collections.FavoriteCollectionService",
        return_value=service,
    ):
        response = authenticated_client.get(
            f"/api/v1/users/me/favorite-collections/{COLLECTION_ID}"
        )
    assert response.status_code == 200
    assert response.json()["data"] == []
    service.get_collection_places.assert_awaited_once_with(
        user_id=USER_ID,
        collection_id=COLLECTION_ID,
    )


def test_update_favorite_collection_returns_updated(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.update_collection.return_value = (
        make_collection(
            name="부산 원정",
        )
    )

    with patch(
        (
            "app.api.v1.endpoints.favorite_collections."
            "FavoriteCollectionService"
        ),
        return_value=service,
    ):
        response = authenticated_client.patch(
            (
                "/api/v1/users/me/favorite-collections/"
                f"{COLLECTION_ID}"
            ),
            json={
                "name": "부산 원정",
            },
        )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert body["data"]["name"] == "부산 원정"

    arguments = (
        service.update_collection.call_args.kwargs
    )

    assert arguments["user_id"] == USER_ID
    assert arguments["collection_id"] == COLLECTION_ID
    assert arguments["request"].name == "부산 원정"


def test_delete_favorite_collection_returns_no_content(
    authenticated_client: TestClient,
) -> None:
    service = Mock()

    with patch(
        (
            "app.api.v1.endpoints.favorite_collections."
            "FavoriteCollectionService"
        ),
        return_value=service,
    ):
        response = authenticated_client.delete(
            (
                "/api/v1/users/me/favorite-collections/"
                f"{COLLECTION_ID}"
            )
        )

    assert response.status_code == 204
    assert response.content == b""

    service.delete_collection.assert_called_once_with(
        user_id=USER_ID,
        collection_id=COLLECTION_ID,
    )


def test_favorite_collections_require_authentication() -> None:
    app.dependency_overrides.clear()

    with TestClient(app) as client:
        response = client.get(
            "/api/v1/users/me/favorite-collections"
        )

    assert response.status_code == 401

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "AUTH_TOKEN_MISSING"


def test_save_favorite_collection_item_returns_saved_item(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.save_item.return_value = (
        FavoriteCollectionItemDocument(
            place_id="tour_123456",
            created_at=FIXED_TIME,
        )
    )

    with patch(
        (
            "app.api.v1.endpoints.favorite_collections."
            "FavoriteCollectionService"
        ),
        return_value=service,
    ):
        response = authenticated_client.put(
            (
                "/api/v1/users/me/favorite-collections/"
                f"{COLLECTION_ID}/items/tour_123456"
            )
        )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert body["data"] == {
        "placeId": "tour_123456",
        "createdAt": "2026-08-20T19:00:00+09:00",
    }

    service.save_item.assert_called_once_with(
        user_id=USER_ID,
        collection_id=COLLECTION_ID,
        place_id="tour_123456",
    )


def test_delete_favorite_collection_item_returns_no_content(
    authenticated_client: TestClient,
) -> None:
    service = Mock()

    with patch(
        (
            "app.api.v1.endpoints.favorite_collections."
            "FavoriteCollectionService"
        ),
        return_value=service,
    ):
        response = authenticated_client.delete(
            (
                "/api/v1/users/me/favorite-collections/"
                f"{COLLECTION_ID}/items/tour_123456"
            )
        )

    assert response.status_code == 204
    assert response.content == b""

    service.delete_item.assert_called_once_with(
        user_id=USER_ID,
        collection_id=COLLECTION_ID,
        place_id="tour_123456",
    )

from datetime import datetime, timezone

from app.schemas.favorite_collection import (
    FavoriteCollectionDocument,
    FavoriteCollectionItemDocument,
)


def test_personal_collection_does_not_store_team_or_region_metadata() -> None:
    now = datetime.now(timezone.utc)
    collection = FavoriteCollectionDocument(
        name="가보고 싶은 장소",
        created_at=now,
        updated_at=now,
    )

    assert collection.model_dump() == {
        "name": "가보고 싶은 장소",
        "createdAt": now,
        "updatedAt": now,
    }


def test_favorite_item_only_references_place() -> None:
    item = FavoriteCollectionItemDocument(
        place_id="tour_123456",
        created_at=datetime.now(timezone.utc),
    )

    assert item.model_dump() == {
        "placeId": "tour_123456",
        "createdAt": item.created_at,
    }

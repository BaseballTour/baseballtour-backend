from datetime import datetime, timezone

from app.schemas.favorite_collection import (
    FavoriteCollectionDocument,
    FavoriteCollectionItemDocument,
)


def test_team_collection_can_reference_regions_and_stadiums() -> None:
    now = datetime.now(timezone.utc)
    collection = FavoriteCollectionDocument(
        name="한화 원정",
        team_id="hanwha",
        stadium_ids=["daejeon"],
        region_codes=["daejeon"],
        created_at=now,
        updated_at=now,
    )

    assert collection.team_id == "hanwha"
    assert collection.stadium_ids == ["daejeon"]


def test_favorite_item_only_references_place() -> None:
    item = FavoriteCollectionItemDocument(
        place_id="tour_123456",
        created_at=datetime.now(timezone.utc),
    )

    assert item.model_dump() == {
        "placeId": "tour_123456",
        "createdAt": item.created_at,
    }

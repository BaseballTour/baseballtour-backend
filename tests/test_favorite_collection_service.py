from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.exceptions import AppException
from app.models.place import Place, PlaceCategory, PlaceSource
from app.schemas.favorite_collection import (
    FavoriteCollectionCreateRequest,
    FavoriteCollectionDocument,
    FavoriteCollectionItemDocument,
    FavoriteCollectionRecord,
    FavoriteCollectionUpdateRequest,
)
from app.services.favorite_collection_service import (
    FavoriteCollectionService,
)


USER_ID = "user_001"
COLLECTION_ID = "collection_001"

FIXED_TIME = datetime(
    2026,
    8,
    20,
    10,
    0,
    tzinfo=timezone.utc,
)


class StubFavoriteCollectionRepository:
    def __init__(self) -> None:
        self.collections: dict[
            tuple[str, str],
            FavoriteCollectionRecord,
        ] = {}
        self.next_id = 0
        self.items: dict[
            tuple[str, str, str],
            FavoriteCollectionItemDocument,
        ] = {}

    def create(
        self,
        *,
        user_id: str,
        collection: FavoriteCollectionDocument,
    ) -> FavoriteCollectionRecord:
        self.next_id += 1

        record = FavoriteCollectionRecord(
            collection_id=f"collection_{self.next_id:03d}",
            **collection.model_dump(),
        )

        self.collections[
            (user_id, record.collection_id)
        ] = record

        return record

    def get_all(
        self,
        *,
        user_id: str,
    ) -> list[FavoriteCollectionRecord]:
        return [
            collection
            for (stored_user_id, _), collection
            in self.collections.items()
            if stored_user_id == user_id
        ]

    def get_by_id(
        self,
        *,
        user_id: str,
        collection_id: str,
    ) -> FavoriteCollectionRecord | None:
        return self.collections.get(
            (user_id, collection_id)
        )

    def update_name(
        self,
        *,
        user_id: str,
        collection_id: str,
        name: str,
        updated_at: datetime,
    ) -> bool:
        key = (
            user_id,
            collection_id,
        )

        existing = self.collections.get(key)

        if existing is None:
            return False

        self.collections[key] = existing.model_copy(
            update={
                "name": name,
                "updated_at": updated_at,
            }
        )

        return True

    def delete(
        self,
        *,
        user_id: str,
        collection_id: str,
    ) -> None:
        self.collections.pop(
            (user_id, collection_id),
            None,
        )


    def save_item(
        self,
        *,
        user_id: str,
        collection_id: str,
        item: FavoriteCollectionItemDocument,
    ) -> FavoriteCollectionItemDocument:
        key = (
            user_id,
            collection_id,
            item.place_id,
        )

        existing = self.items.get(key)

        if existing is not None:
            return existing

        self.items[key] = item
        return item

    def get_items(
        self,
        *,
        user_id: str,
        collection_id: str,
    ) -> list[FavoriteCollectionItemDocument]:
        return [
            item
            for (
                stored_user_id,
                stored_collection_id,
                _,
            ), item in self.items.items()
            if stored_user_id == user_id
            and stored_collection_id == collection_id
        ]

    def update_item_snapshot(
        self,
        *,
        user_id: str,
        collection_id: str,
        place_id: str,
        place_snapshot: Place,
    ) -> None:
        key = (user_id, collection_id, place_id)
        existing = self.items[key]
        self.items[key] = existing.model_copy(
            update={"place_snapshot": place_snapshot}
        )

    def delete_item(
        self,
        *,
        user_id: str,
        collection_id: str,
        place_id: str,
    ) -> bool:
        key = (
            user_id,
            collection_id,
            place_id,
        )

        if key not in self.items:
            return False

        del self.items[key]
        return True


def create_service() -> tuple[
    FavoriteCollectionService,
    StubFavoriteCollectionRepository,
]:
    repository = StubFavoriteCollectionRepository()
    place_adapter = Mock()
    place_adapter.get_place_detail = AsyncMock(
        return_value=Place(
            place_id="tour_123456",
            name="테스트 장소",
            category=PlaceCategory.TOURIST_SPOT,
            latitude=37.5,
            longitude=127.0,
            address="서울특별시",
            source=PlaceSource.TOUR_API,
            source_content_id="123456",
        )
    )

    service = FavoriteCollectionService(
        repository=repository,
        place_adapter=place_adapter,
    )

    return service, repository


def seed_collection(
    repository: StubFavoriteCollectionRepository,
) -> FavoriteCollectionRecord:
    record = FavoriteCollectionRecord(
        collection_id=COLLECTION_ID,
        name="가보고 싶은 장소",
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
    )

    repository.collections[
        (USER_ID, COLLECTION_ID)
    ] = record

    return record


def test_create_collection_saves_personal_collection() -> None:
    service, _ = create_service()

    created = service.create_collection(
        user_id=USER_ID,
        request=FavoriteCollectionCreateRequest(
            name="가보고 싶은 장소",
        ),
    )

    assert created.name == "가보고 싶은 장소"
    assert created.created_at.tzinfo is not None
    assert created.updated_at.tzinfo is not None


def test_get_collections_returns_user_collections() -> None:
    service, repository = create_service()

    seed_collection(repository)

    collections = service.get_collections(
        user_id=USER_ID
    )

    assert len(collections) == 1
    assert collections[0].collection_id == COLLECTION_ID


def test_update_collection_changes_name() -> None:
    service, repository = create_service()

    seed_collection(repository)

    before_update = datetime.now(timezone.utc)

    updated = service.update_collection(
        user_id=USER_ID,
        collection_id=COLLECTION_ID,
        request=FavoriteCollectionUpdateRequest(
            name="부산 원정 맛집",
        ),
    )

    after_update = datetime.now(timezone.utc)

    assert updated.name == "부산 원정 맛집"
    assert before_update <= updated.updated_at <= after_update


def test_update_missing_collection_raises_not_found() -> None:
    service, _ = create_service()

    with pytest.raises(AppException) as exception_info:
        service.update_collection(
            user_id=USER_ID,
            collection_id="missing",
            request=FavoriteCollectionUpdateRequest(
                name="새 이름",
            ),
        )

    exception = exception_info.value

    assert exception.status_code == 404
    assert (
        exception.code
        == "FAVORITE_COLLECTION_NOT_FOUND"
    )


def test_delete_collection_removes_collection() -> None:
    service, repository = create_service()

    seed_collection(repository)

    service.delete_collection(
        user_id=USER_ID,
        collection_id=COLLECTION_ID,
    )

    assert repository.get_by_id(
        user_id=USER_ID,
        collection_id=COLLECTION_ID,
    ) is None


def test_delete_missing_collection_raises_not_found() -> None:
    service, _ = create_service()

    with pytest.raises(AppException) as exception_info:
        service.delete_collection(
            user_id=USER_ID,
            collection_id="missing",
        )

    exception = exception_info.value

    assert exception.status_code == 404
    assert (
        exception.code
        == "FAVORITE_COLLECTION_NOT_FOUND"
    )


@pytest.mark.anyio
async def test_save_item_saves_tour_place_snapshot() -> None:
    service, repository = create_service()
    seed_collection(repository)

    item = await service.save_item(
        user_id=USER_ID,
        collection_id=COLLECTION_ID,
        place_id="tour_123456",
    )

    assert item.place_id == "tour_123456"
    assert item.place_snapshot is not None
    assert item.place_snapshot.name == "테스트 장소"
    assert item.created_at.tzinfo is not None

    assert repository.get_items(
        user_id=USER_ID,
        collection_id=COLLECTION_ID,
    ) == [item]


@pytest.mark.anyio
async def test_save_item_rejects_non_tour_place() -> None:
    service, repository = create_service()
    seed_collection(repository)

    with pytest.raises(AppException) as exception_info:
        await service.save_item(
            user_id=USER_ID,
            collection_id=COLLECTION_ID,
            place_id="kakao_123456",
        )

    exception = exception_info.value

    assert exception.status_code == 422
    assert exception.code == "INVALID_FAVORITE_PLACE"


@pytest.mark.anyio
async def test_save_item_missing_collection_raises_not_found() -> None:
    service, _ = create_service()

    with pytest.raises(AppException) as exception_info:
        await service.save_item(
            user_id=USER_ID,
            collection_id="missing",
            place_id="tour_123456",
        )

    exception = exception_info.value

    assert exception.status_code == 404
    assert (
        exception.code
        == "FAVORITE_COLLECTION_NOT_FOUND"
    )


@pytest.mark.anyio
async def test_delete_item_removes_saved_place() -> None:
    service, repository = create_service()
    seed_collection(repository)

    await service.save_item(
        user_id=USER_ID,
        collection_id=COLLECTION_ID,
        place_id="tour_123456",
    )

    service.delete_item(
        user_id=USER_ID,
        collection_id=COLLECTION_ID,
        place_id="tour_123456",
    )

    assert repository.get_items(
        user_id=USER_ID,
        collection_id=COLLECTION_ID,
    ) == []


def test_delete_missing_item_raises_not_found() -> None:
    service, repository = create_service()
    seed_collection(repository)

    with pytest.raises(AppException) as exception_info:
        service.delete_item(
            user_id=USER_ID,
            collection_id=COLLECTION_ID,
            place_id="tour_missing",
        )

    exception = exception_info.value

    assert exception.status_code == 404
    assert (
        exception.code
        == "FAVORITE_COLLECTION_ITEM_NOT_FOUND"
    )


@pytest.mark.anyio
async def test_collection_places_use_snapshot_without_external_api() -> None:
    repository = StubFavoriteCollectionRepository()
    seed_collection(repository)
    snapshot = Place(
        place_id="tour_123456",
        name="저장된 장소",
        category=PlaceCategory.TOURIST_SPOT,
        latitude=37.5,
        longitude=127.0,
        source=PlaceSource.TOUR_API,
        source_content_id="123456",
    )
    repository.items[(USER_ID, COLLECTION_ID, snapshot.place_id)] = (
        FavoriteCollectionItemDocument(
            place_id=snapshot.place_id,
            place_snapshot=snapshot,
            created_at=FIXED_TIME,
        )
    )
    adapter = Mock()
    adapter.get_place_detail = AsyncMock()
    service = FavoriteCollectionService(
        repository=repository,
        place_adapter=adapter,
    )

    places = await service.get_collection_places(
        user_id=USER_ID,
        collection_id=COLLECTION_ID,
    )

    assert places == [snapshot]
    adapter.get_place_detail.assert_not_awaited()


@pytest.mark.anyio
async def test_legacy_collection_item_failure_does_not_fail_whole_request() -> None:
    repository = StubFavoriteCollectionRepository()
    seed_collection(repository)
    repository.items[(USER_ID, COLLECTION_ID, "tour_legacy")] = (
        FavoriteCollectionItemDocument(
            place_id="tour_legacy",
            created_at=FIXED_TIME,
        )
    )
    adapter = Mock()
    adapter.get_place_detail = AsyncMock(
        side_effect=AppException(
            status_code=503,
            code="EXTERNAL_API_TIMEOUT",
            message="TourAPI 요청 시간이 초과되었습니다.",
        )
    )
    service = FavoriteCollectionService(
        repository=repository,
        place_adapter=adapter,
    )

    places = await service.get_collection_places(
        user_id=USER_ID,
        collection_id=COLLECTION_ID,
    )

    assert places == []

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

    def create_if_absent(
        self,
        *,
        user_id: str,
        collection_id: str,
        collection: FavoriteCollectionDocument,
    ) -> FavoriteCollectionRecord:
        key = (user_id, collection_id)

        existing = self.collections.get(key)
        if existing is not None:
            return existing

        record = FavoriteCollectionRecord(
            collection_id=collection_id,
            **collection.model_dump(),
        )
        self.collections[key] = record
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

    def has_item(
        self,
        *,
        user_id: str,
        collection_id: str,
        place_id: str,
    ) -> bool:
        return (
            user_id,
            collection_id,
            place_id,
        ) in self.items

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

    assert len(collections) == 2
    assert {
        collection.collection_id
        for collection in collections
    } == {
        COLLECTION_ID,
        FavoriteCollectionService.DEFAULT_COLLECTION_ID,
    }


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


def test_ensure_default_collection_creates_saved_collection() -> None:
    service, repository = create_service()

    created = service.ensure_default_collection(
        user_id=USER_ID,
    )

    assert (
        created.collection_id
        == FavoriteCollectionService.DEFAULT_COLLECTION_ID
    )
    assert created.name == "저장됨"
    assert created.is_default is True

    stored = repository.get_by_id(
        user_id=USER_ID,
        collection_id=(
            FavoriteCollectionService.DEFAULT_COLLECTION_ID
        ),
    )

    assert stored is not None
    assert stored.name == "저장됨"
    assert stored.is_default is True


def test_get_collections_repairs_missing_default_idempotently() -> None:
    service, repository = create_service()

    first = service.get_collections(
        user_id=USER_ID,
    )
    second = service.get_collections(
        user_id=USER_ID,
    )

    assert len(first) == 1
    assert len(second) == 1

    assert (
        first[0].collection_id
        == FavoriteCollectionService.DEFAULT_COLLECTION_ID
    )
    assert first[0].name == "저장됨"
    assert first[0].is_default is True

    defaults = [
        collection
        for (stored_user_id, _), collection
        in repository.collections.items()
        if stored_user_id == USER_ID
        and collection.is_default
    ]

    assert len(defaults) == 1


def test_user_collection_named_saved_is_distinct_from_default() -> None:
    service, _ = create_service()

    personal = service.create_collection(
        user_id=USER_ID,
        request=FavoriteCollectionCreateRequest(
            name="저장됨",
        ),
    )

    collections = service.get_collections(
        user_id=USER_ID,
    )

    assert len(collections) == 2
    assert personal.is_default is False

    default = next(
        collection
        for collection in collections
        if collection.is_default
    )

    assert (
        default.collection_id
        == FavoriteCollectionService.DEFAULT_COLLECTION_ID
    )
    assert default.name == "저장됨"
    assert default.collection_id != personal.collection_id


def test_update_default_collection_is_rejected() -> None:
    service, _ = create_service()

    default = service.ensure_default_collection(
        user_id=USER_ID,
    )

    with pytest.raises(AppException) as exc_info:
        service.update_collection(
            user_id=USER_ID,
            collection_id=default.collection_id,
            request=FavoriteCollectionUpdateRequest(
                name="다른 이름",
            ),
        )

    assert exc_info.value.status_code == 409
    assert (
        exc_info.value.code
        == "DEFAULT_FAVORITE_COLLECTION_IMMUTABLE"
    )


def test_delete_default_collection_is_rejected() -> None:
    service, repository = create_service()

    default = service.ensure_default_collection(
        user_id=USER_ID,
    )

    with pytest.raises(AppException) as exc_info:
        service.delete_collection(
            user_id=USER_ID,
            collection_id=default.collection_id,
        )

    assert exc_info.value.status_code == 409
    assert (
        exc_info.value.code
        == "DEFAULT_FAVORITE_COLLECTION_IMMUTABLE"
    )

    assert repository.get_by_id(
        user_id=USER_ID,
        collection_id=default.collection_id,
    ) is not None


@pytest.mark.anyio
async def test_collection_summary_uses_snapshot_and_count() -> None:
    repository = StubFavoriteCollectionRepository()
    collection = seed_collection(repository)

    first_place = Place(
        place_id="tour_100001",
        name="첫 번째 장소",
        category=PlaceCategory.TOURIST_SPOT,
        latitude=37.5,
        longitude=127.0,
        address="서울특별시",
        thumbnail_url="https://example.com/first.jpg",
        source=PlaceSource.TOUR_API,
        source_content_id="100001",
    )
    second_place = Place(
        place_id="tour_100002",
        name="두 번째 장소",
        category=PlaceCategory.TOURIST_SPOT,
        latitude=37.6,
        longitude=127.1,
        address="서울특별시",
        source=PlaceSource.TOUR_API,
        source_content_id="100002",
    )

    repository.items[
        (USER_ID, COLLECTION_ID, first_place.place_id)
    ] = FavoriteCollectionItemDocument(
        place_id=first_place.place_id,
        place_snapshot=first_place,
        created_at=FIXED_TIME,
    )
    repository.items[
        (USER_ID, COLLECTION_ID, second_place.place_id)
    ] = FavoriteCollectionItemDocument(
        place_id=second_place.place_id,
        place_snapshot=second_place,
        created_at=FIXED_TIME,
    )

    adapter = Mock()
    adapter.get_place_detail = AsyncMock()

    service = FavoriteCollectionService(
        repository=repository,
        place_adapter=adapter,
    )

    summary = await service.get_collection_summary(
        user_id=USER_ID,
        collection=collection,
    )

    assert summary.collection_id == COLLECTION_ID
    assert summary.place_count == 2
    assert summary.representative_place_name == "첫 번째 장소"
    assert summary.thumbnail_url == "https://example.com/first.jpg"
    adapter.get_place_detail.assert_not_awaited()


@pytest.mark.anyio
async def test_collection_summary_empty_collection() -> None:
    service, repository = create_service()
    collection = seed_collection(repository)

    summary = await service.get_collection_summary(
        user_id=USER_ID,
        collection=collection,
    )

    assert summary.place_count == 0
    assert summary.representative_place_name is None
    assert summary.thumbnail_url is None


@pytest.mark.anyio
async def test_collection_summary_backfills_legacy_snapshot() -> None:
    repository = StubFavoriteCollectionRepository()
    collection = seed_collection(repository)

    repository.items[
        (USER_ID, COLLECTION_ID, "tour_123456")
    ] = FavoriteCollectionItemDocument(
        place_id="tour_123456",
        created_at=FIXED_TIME,
    )

    place = Place(
        place_id="tour_123456",
        name="보충된 장소",
        category=PlaceCategory.TOURIST_SPOT,
        latitude=37.5,
        longitude=127.0,
        address="서울특별시",
        thumbnail_url="https://example.com/backfilled.jpg",
        source=PlaceSource.TOUR_API,
        source_content_id="123456",
    )

    adapter = Mock()
    adapter.get_place_detail = AsyncMock(
        return_value=place,
    )

    service = FavoriteCollectionService(
        repository=repository,
        place_adapter=adapter,
    )

    summary = await service.get_collection_summary(
        user_id=USER_ID,
        collection=collection,
    )

    assert summary.place_count == 1
    assert summary.representative_place_name == "보충된 장소"
    assert summary.thumbnail_url == "https://example.com/backfilled.jpg"

    adapter.get_place_detail.assert_awaited_once_with("123456")

    stored = repository.items[
        (USER_ID, COLLECTION_ID, "tour_123456")
    ]
    assert stored.place_snapshot == place


def test_get_collections_for_place_returns_matching_collections() -> None:
    service, repository = create_service()

    first = seed_collection(repository)

    second = FavoriteCollectionRecord(
        collection_id="collection_002",
        name="부산 맛집",
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
    )
    repository.collections[
        (USER_ID, second.collection_id)
    ] = second

    item = FavoriteCollectionItemDocument(
        place_id="tour_123456",
        created_at=FIXED_TIME,
    )

    repository.items[
        (USER_ID, first.collection_id, item.place_id)
    ] = item
    repository.items[
        (USER_ID, second.collection_id, item.place_id)
    ] = item

    result = service.get_collections_for_place(
        user_id=USER_ID,
        place_id="tour_123456",
    )

    assert result.place_id == "tour_123456"
    assert result.count == 2
    assert set(result.collection_ids) == {
        first.collection_id,
        second.collection_id,
    }


def test_get_collections_for_place_returns_empty_when_not_saved() -> None:
    service, repository = create_service()
    seed_collection(repository)

    result = service.get_collections_for_place(
        user_id=USER_ID,
        place_id="tour_999999",
    )

    assert result.place_id == "tour_999999"
    assert result.collection_ids == []
    assert result.count == 0


def test_get_collections_for_place_rejects_non_tour_place() -> None:
    service, _ = create_service()

    with pytest.raises(AppException) as exception_info:
        service.get_collections_for_place(
            user_id=USER_ID,
            place_id="kakao_123456",
        )

    exception = exception_info.value
    assert exception.status_code == 422
    assert exception.code == "INVALID_FAVORITE_PLACE"

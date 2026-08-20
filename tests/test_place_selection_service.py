from datetime import datetime, timezone

import pytest

from app.core.exceptions import AppException
from app.models.place import Place
from app.schemas.favorite_collection import (
    FavoriteCollectionItemDocument,
    FavoriteCollectionRecord,
)
from app.schemas.game import GameRecord
from app.schemas.stadium import StadiumResponse
from app.schemas.place_selection import (
    PlaceSelectionCreateRequest,
    PlaceSelectionDocument,
    PlaceSelectionRecord,
)
from app.schemas.trip import TripRecord
from app.services.place_selection_service import (
    PlaceSelectionService,
)


USER_ID = "user-001"
TRIP_ID = "trip-001"
PLACE_ID = "tour_123456"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class StubTripRepository:
    def __init__(
        self,
        trips: list[TripRecord] | None = None,
    ) -> None:
        self._trips = {
            trip.trip_id: trip
            for trip in (trips or [])
        }

    def get_by_id(
        self,
        trip_id: str,
    ) -> TripRecord | None:
        return self._trips.get(trip_id)


class StubPlaceSelectionRepository:
    def __init__(self) -> None:
        self._selections: dict[
            tuple[str, str],
            PlaceSelectionRecord,
        ] = {}

    def create(
        self,
        *,
        trip_id: str,
        selection: PlaceSelectionDocument,
    ) -> PlaceSelectionRecord | None:
        key = (
            trip_id,
            selection.place_id,
        )

        if key in self._selections:
            return None

        record = PlaceSelectionRecord(
            **selection.model_dump()
        )
        self._selections[key] = record

        return record

    def get_all(
        self,
        *,
        trip_id: str,
    ) -> list[PlaceSelectionRecord]:
        return [
            selection
            for (stored_trip_id, _), selection
            in self._selections.items()
            if stored_trip_id == trip_id
        ]

    def update_required(
        self,
        *,
        trip_id: str,
        place_id: str,
        is_required: bool,
    ) -> PlaceSelectionRecord | None:
        key = (
            trip_id,
            place_id,
        )

        existing = self._selections.get(key)

        if existing is None:
            return None

        updated = existing.model_copy(
            update={
                "is_required": is_required,
            }
        )

        self._selections[key] = updated

        return updated

    def delete(
        self,
        *,
        trip_id: str,
        place_id: str,
    ) -> bool:
        key = (
            trip_id,
            place_id,
        )

        if key not in self._selections:
            return False

        del self._selections[key]
        return True


def make_trip(
    *,
    trip_id: str = TRIP_ID,
    user_id: str = USER_ID,
) -> TripRecord:
    now = datetime.now(timezone.utc)

    return TripRecord(
        trip_id=trip_id,
        user_id=user_id,
        game_id="dev_game_20260815_lotte_doosan",
        title="부산 원정",
        trip_start_at=datetime(
            2026,
            8,
            14,
            tzinfo=timezone.utc,
        ),
        trip_end_at=datetime(
            2026,
            8,
            16,
            tzinfo=timezone.utc,
        ),
        arrival_point=None,
        departure_point=None,
        accommodation=None,
        status="PLANNING",
        active_plan_id=None,
        created_at=now,
        updated_at=now,
    )


def create_service(
    *,
    trips: list[TripRecord] | None = None,
) -> tuple[
    PlaceSelectionService,
    StubPlaceSelectionRepository,
]:
    selection_repository = (
        StubPlaceSelectionRepository()
    )

    service = PlaceSelectionService(
        place_selection_repository=selection_repository,
        trip_repository=StubTripRepository(
            trips=(
                trips
                if trips is not None
                else [make_trip()]
            )
        ),
    )

    return service, selection_repository


def test_create_selection_saves_place() -> None:
    service, _ = create_service()

    selection = service.create_selection(
        user_id=USER_ID,
        trip_id=TRIP_ID,
        request=PlaceSelectionCreateRequest(
            place_id=PLACE_ID,
            is_required=True,
        ),
    )

    assert selection.place_id == PLACE_ID
    assert selection.is_required is True
    assert selection.created_at.tzinfo is not None


def test_create_selection_rejects_duplicate() -> None:
    service, _ = create_service()

    request = PlaceSelectionCreateRequest(
        place_id=PLACE_ID,
        is_required=False,
    )

    service.create_selection(
        user_id=USER_ID,
        trip_id=TRIP_ID,
        request=request,
    )

    with pytest.raises(AppException) as exception_info:
        service.create_selection(
            user_id=USER_ID,
            trip_id=TRIP_ID,
            request=request,
        )

    exception = exception_info.value

    assert exception.status_code == 409
    assert (
        exception.code
        == "PLACE_SELECTION_ALREADY_EXISTS"
    )


def test_get_selections_returns_trip_selections() -> None:
    service, _ = create_service()

    service.create_selection(
        user_id=USER_ID,
        trip_id=TRIP_ID,
        request=PlaceSelectionCreateRequest(
            place_id="tour_001",
        ),
    )
    service.create_selection(
        user_id=USER_ID,
        trip_id=TRIP_ID,
        request=PlaceSelectionCreateRequest(
            place_id="tour_002",
        ),
    )

    selections = service.get_selections(
        user_id=USER_ID,
        trip_id=TRIP_ID,
    )

    assert {
        selection.place_id
        for selection in selections
    } == {
        "tour_001",
        "tour_002",
    }


def test_delete_selection_removes_place() -> None:
    service, _ = create_service()

    service.create_selection(
        user_id=USER_ID,
        trip_id=TRIP_ID,
        request=PlaceSelectionCreateRequest(
            place_id=PLACE_ID,
        ),
    )

    service.delete_selection(
        user_id=USER_ID,
        trip_id=TRIP_ID,
        place_id=PLACE_ID,
    )

    assert service.get_selections(
        user_id=USER_ID,
        trip_id=TRIP_ID,
    ) == []


def test_delete_missing_selection_raises_not_found() -> None:
    service, _ = create_service()

    with pytest.raises(AppException) as exception_info:
        service.delete_selection(
            user_id=USER_ID,
            trip_id=TRIP_ID,
            place_id="tour_missing",
        )

    exception = exception_info.value

    assert exception.status_code == 404
    assert exception.code == "PLACE_SELECTION_NOT_FOUND"


def test_missing_trip_raises_not_found() -> None:
    service, _ = create_service(
        trips=[],
    )

    with pytest.raises(AppException) as exception_info:
        service.get_selections(
            user_id=USER_ID,
            trip_id="missing",
        )

    exception = exception_info.value

    assert exception.status_code == 404
    assert exception.code == "TRIP_NOT_FOUND"


def test_other_user_trip_raises_access_denied() -> None:
    service, _ = create_service(
        trips=[
            make_trip(
                user_id="other-user",
            )
        ],
    )

    with pytest.raises(AppException) as exception_info:
        service.get_selections(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    exception = exception_info.value

    assert exception.status_code == 403
    assert exception.code == "TRIP_ACCESS_DENIED"


class StubFavoriteCollectionImportRepository:
    def __init__(
        self,
        *,
        exists: bool = True,
        place_ids: list[str] | None = None,
    ) -> None:
        self.exists = exists
        self.place_ids = place_ids or []

    def get_by_id(
        self,
        *,
        user_id: str,
        collection_id: str,
    ) -> FavoriteCollectionRecord | None:
        if not self.exists:
            return None

        now = datetime.now(timezone.utc)

        return FavoriteCollectionRecord(
            collection_id=collection_id,
            name="테스트 찜",
            created_at=now,
            updated_at=now,
        )

    def get_items(
        self,
        *,
        user_id: str,
        collection_id: str,
    ) -> list[FavoriteCollectionItemDocument]:
        now = datetime.now(timezone.utc)

        return [
            FavoriteCollectionItemDocument(
                place_id=place_id,
                created_at=now,
            )
            for place_id in self.place_ids
        ]


class StubGameImportRepository:
    def __init__(
        self,
        game: GameRecord | None,
    ) -> None:
        self.game = game

    def get_by_id(
        self,
        game_id: str,
    ) -> GameRecord | None:
        if (
            self.game is not None
            and self.game.game_id == game_id
        ):
            return self.game

        return None


class StubStadiumImportRepository:
    def __init__(
        self,
        stadium: StadiumResponse | None,
    ) -> None:
        self.stadium = stadium

    def get_by_id(
        self,
        stadium_id: str,
    ) -> StadiumResponse | None:
        if (
            self.stadium is not None
            and self.stadium.stadium_id == stadium_id
        ):
            return self.stadium

        return None


class StubPlaceImportAdapter:
    def __init__(
        self,
        places: dict[str, Place | Exception],
    ) -> None:
        self.places = places
        self.requested_content_ids: list[str] = []

    async def get_place_detail(
        self,
        content_id: str,
    ) -> Place:
        self.requested_content_ids.append(content_id)

        result = self.places.get(content_id)

        if result is None:
            raise ValueError("장소 없음")

        if isinstance(result, Exception):
            raise result

        return result


def make_import_game(
    *,
    stadium_id: str = "sajik",
) -> GameRecord:
    now = datetime.now(timezone.utc)

    return GameRecord(
        game_id="dev_game_20260815_lotte_doosan",
        home_team_id="lotte",
        away_team_id="doosan",
        stadium_id=stadium_id,
        game_start_at=datetime(
            2026,
            8,
            15,
            9,
            0,
            tzinfo=timezone.utc,
        ),
        status="SCHEDULED",
        home_score=None,
        away_score=None,
        result_text=None,
        created_at=now,
        updated_at=now,
    )


def make_import_stadium(
    *,
    stadium_id: str = "sajik",
    region: str = "부산",
) -> StadiumResponse:
    now = datetime.now(timezone.utc)

    return StadiumResponse(
        stadium_id=stadium_id,
        name="사직야구장",
        address="부산광역시 동래구 사직로 45",
        latitude=35.194,
        longitude=129.0615,
        region=region,
        created_at=now,
        updated_at=now,
    )


def make_import_place(
    *,
    content_id: str,
    address: str,
) -> Place:
    return Place(
        place_id=f"tour_{content_id}",
        name=f"장소 {content_id}",
        latitude=35.18,
        longitude=129.07,
        address=address,
        source_content_id=content_id,
    )


def create_import_service(
    *,
    place_ids: list[str],
    places: dict[str, Place | Exception],
    collection_exists: bool = True,
    trip_user_id: str = USER_ID,
    game: GameRecord | None = None,
    stadium: StadiumResponse | None = None,
) -> tuple[
    PlaceSelectionService,
    StubPlaceSelectionRepository,
    StubPlaceImportAdapter,
]:
    selection_repository = StubPlaceSelectionRepository()

    place_adapter = StubPlaceImportAdapter(
        places=places
    )

    service = PlaceSelectionService(
        place_selection_repository=selection_repository,
        trip_repository=StubTripRepository(
            trips=[
                make_trip(
                    user_id=trip_user_id,
                )
            ]
        ),
        favorite_collection_repository=(
            StubFavoriteCollectionImportRepository(
                exists=collection_exists,
                place_ids=place_ids,
            )
        ),
        game_repository=StubGameImportRepository(
            game=(
                game
                if game is not None
                else make_import_game()
            )
        ),
        stadium_repository=StubStadiumImportRepository(
            stadium=(
                stadium
                if stadium is not None
                else make_import_stadium()
            )
        ),
        place_adapter=place_adapter,
    )

    return (
        service,
        selection_repository,
        place_adapter,
    )


@pytest.mark.anyio
async def test_import_favorite_collection_adds_same_region_place() -> None:
    service, repository, _ = create_import_service(
        place_ids=[
            "tour_100",
        ],
        places={
            "100": make_import_place(
                content_id="100",
                address="부산광역시 수영구 광안해변로",
            ),
        },
    )

    imported = await service.import_from_favorite_collection(
        user_id=USER_ID,
        trip_id=TRIP_ID,
        collection_id="collection_001",
    )

    assert len(imported) == 1
    assert imported[0].place_id == "tour_100"
    assert imported[0].is_required is False

    stored = repository.get_all(
        trip_id=TRIP_ID
    )

    assert len(stored) == 1
    assert stored[0].place_id == "tour_100"


@pytest.mark.anyio
async def test_import_favorite_collection_excludes_other_region() -> None:
    service, repository, _ = create_import_service(
        place_ids=[
            "tour_100",
        ],
        places={
            "100": make_import_place(
                content_id="100",
                address="서울특별시 송파구 올림픽로",
            ),
        },
    )

    imported = await service.import_from_favorite_collection(
        user_id=USER_ID,
        trip_id=TRIP_ID,
        collection_id="collection_001",
    )

    assert imported == []
    assert repository.get_all(
        trip_id=TRIP_ID
    ) == []


@pytest.mark.anyio
async def test_import_favorite_collection_excludes_unknown_region() -> None:
    service, repository, _ = create_import_service(
        place_ids=[
            "tour_100",
        ],
        places={
            "100": make_import_place(
                content_id="100",
                address="",
            ),
        },
    )

    imported = await service.import_from_favorite_collection(
        user_id=USER_ID,
        trip_id=TRIP_ID,
        collection_id="collection_001",
    )

    assert imported == []
    assert repository.get_all(
        trip_id=TRIP_ID
    ) == []


@pytest.mark.anyio
async def test_import_favorite_collection_skips_existing_selection() -> None:
    service, repository, adapter = create_import_service(
        place_ids=[
            "tour_100",
        ],
        places={
            "100": make_import_place(
                content_id="100",
                address="부산광역시 동래구",
            ),
        },
    )

    repository.create(
        trip_id=TRIP_ID,
        selection=PlaceSelectionDocument(
            place_id="tour_100",
            is_required=True,
            created_at=datetime.now(timezone.utc),
        ),
    )

    imported = await service.import_from_favorite_collection(
        user_id=USER_ID,
        trip_id=TRIP_ID,
        collection_id="collection_001",
    )

    assert imported == []

    stored = repository.get_all(
        trip_id=TRIP_ID
    )

    assert len(stored) == 1
    assert stored[0].is_required is True

    assert adapter.requested_content_ids == []


@pytest.mark.anyio
async def test_import_favorite_collection_skips_invalid_tour_place() -> None:
    service, repository, _ = create_import_service(
        place_ids=[
            "tour_999",
        ],
        places={
            "999": ValueError("장소 없음"),
        },
    )

    imported = await service.import_from_favorite_collection(
        user_id=USER_ID,
        trip_id=TRIP_ID,
        collection_id="collection_001",
    )

    assert imported == []
    assert repository.get_all(
        trip_id=TRIP_ID
    ) == []


@pytest.mark.anyio
async def test_import_missing_favorite_collection_raises_not_found() -> None:
    service, _, _ = create_import_service(
        place_ids=[],
        places={},
        collection_exists=False,
    )

    with pytest.raises(AppException) as exception_info:
        await service.import_from_favorite_collection(
            user_id=USER_ID,
            trip_id=TRIP_ID,
            collection_id="missing",
        )

    exception = exception_info.value

    assert exception.status_code == 404
    assert (
        exception.code
        == "FAVORITE_COLLECTION_NOT_FOUND"
    )


@pytest.mark.anyio
async def test_import_missing_game_raises_not_found() -> None:
    service, _, _ = create_import_service(
        place_ids=[],
        places={},
        game=StubGameImportRepository(None).game,
    )

    service._game_repository = StubGameImportRepository(
        None
    )

    with pytest.raises(AppException) as exception_info:
        await service.import_from_favorite_collection(
            user_id=USER_ID,
            trip_id=TRIP_ID,
            collection_id="collection_001",
        )

    exception = exception_info.value

    assert exception.status_code == 404
    assert exception.code == "GAME_NOT_FOUND"


@pytest.mark.anyio
async def test_import_missing_stadium_raises_not_found() -> None:
    service, _, _ = create_import_service(
        place_ids=[],
        places={},
    )

    service._stadium_repository = (
        StubStadiumImportRepository(None)
    )

    with pytest.raises(AppException) as exception_info:
        await service.import_from_favorite_collection(
            user_id=USER_ID,
            trip_id=TRIP_ID,
            collection_id="collection_001",
        )

    exception = exception_info.value

    assert exception.status_code == 404
    assert exception.code == "STADIUM_NOT_FOUND"


@pytest.mark.anyio
async def test_import_other_user_trip_raises_access_denied() -> None:
    service, _, _ = create_import_service(
        place_ids=[],
        places={},
        trip_user_id="other-user",
    )

    with pytest.raises(AppException) as exception_info:
        await service.import_from_favorite_collection(
            user_id=USER_ID,
            trip_id=TRIP_ID,
            collection_id="collection_001",
        )

    exception = exception_info.value

    assert exception.status_code == 403
    assert exception.code == "TRIP_ACCESS_DENIED"


def test_update_required_changes_selection() -> None:
    service, _ = create_service()

    service.create_selection(
        user_id=USER_ID,
        trip_id=TRIP_ID,
        request=PlaceSelectionCreateRequest(
            place_id=PLACE_ID,
            is_required=False,
        ),
    )

    updated = service.update_required(
        user_id=USER_ID,
        trip_id=TRIP_ID,
        place_id=PLACE_ID,
        is_required=True,
    )

    assert updated.place_id == PLACE_ID
    assert updated.is_required is True


def test_update_required_missing_selection_raises_not_found() -> None:
    service, _ = create_service()

    with pytest.raises(AppException) as exception_info:
        service.update_required(
            user_id=USER_ID,
            trip_id=TRIP_ID,
            place_id="tour_missing",
            is_required=True,
        )

    exception = exception_info.value

    assert exception.status_code == 404
    assert exception.code == "PLACE_SELECTION_NOT_FOUND"


def test_update_required_other_user_trip_denied() -> None:
    service, _ = create_service(
        trips=[
            make_trip(
                user_id="other-user",
            )
        ],
    )

    with pytest.raises(AppException) as exception_info:
        service.update_required(
            user_id=USER_ID,
            trip_id=TRIP_ID,
            place_id=PLACE_ID,
            is_required=True,
        )

    exception = exception_info.value

    assert exception.status_code == 403
    assert exception.code == "TRIP_ACCESS_DENIED"

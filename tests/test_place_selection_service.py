from datetime import datetime, timezone

import pytest

from app.core.exceptions import AppException
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

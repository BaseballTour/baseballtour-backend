from datetime import datetime, timezone
from typing import Any

import pytest

from app.core.exceptions import AppException
from app.repositories.trip_repository import (
    TripIdempotencyConflictError,
)
from app.schemas.game import GameRecord, GameStatus
from app.schemas.trip import (
    TripCreateRequest,
    TripDocument,
    TripPoint,
    TripRecord,
    TripUpdateRequest,
)
from app.services.trip_service import TripService


GAME_ID = "dev_game_20260815_lotte_doosan"


class StubGameRepository:
    def __init__(
        self,
        games: list[GameRecord],
    ) -> None:
        self._games = {
            game.game_id: game
            for game in games
        }

    def get_by_id(
        self,
        game_id: str,
    ) -> GameRecord | None:
        return self._games.get(game_id)


class StubPlaceSelectionRepository:
    def __init__(self) -> None:
        self.deleted_trip_ids: list[str] = []

    def delete_all(
        self,
        *,
        trip_id: str,
    ) -> int:
        self.deleted_trip_ids.append(trip_id)
        return 0


class StubItineraryPlanRepository:
    def __init__(self) -> None:
        self.deleted_trip_ids: list[str] = []

    def delete_all_by_trip_id(
        self,
        *,
        trip_id: str,
    ) -> int:
        self.deleted_trip_ids.append(trip_id)
        return 0


class StubTripRepository:
    def __init__(self) -> None:
        self._trips: dict[str, TripRecord] = {}
        self._next_id = 1

    def create(
        self,
        trip: TripDocument,
    ) -> TripRecord:
        trip_id = f"trip_auto_{self._next_id:03d}"
        self._next_id += 1

        record = TripRecord(
            trip_id=trip_id,
            **trip.model_dump(),
        )
        self._trips[trip_id] = record

        return record

    def create_idempotent(
        self,
        *,
        trip: TripDocument,
        idempotency_key: str,
    ) -> TripRecord:
        return self.create(trip)

    def get_by_id(
        self,
        trip_id: str,
    ) -> TripRecord | None:
        return self._trips.get(trip_id)

    def get_by_user_id(
        self,
        user_id: str,
    ) -> list[TripRecord]:
        return [
            trip
            for trip in self._trips.values()
            if trip.user_id == user_id
        ]

    def update(
        self,
        trip_id: str,
        updates: dict[str, Any],
    ) -> TripRecord | None:
        current = self._trips.get(trip_id)

        if current is None:
            return None

        data = current.model_dump(
            by_alias=True,
        )
        data.update(updates)

        updated = TripRecord.model_validate(data)
        self._trips[trip_id] = updated

        return updated

    def delete(
        self,
        trip_id: str,
    ) -> bool:
        if trip_id not in self._trips:
            return False

        del self._trips[trip_id]
        return True


def create_game(
    *,
    game_id: str = GAME_ID,
    game_start_at: datetime | None = None,
) -> GameRecord:
    now = datetime.now(timezone.utc)

    return GameRecord(
        game_id=game_id,
        home_team_id="lotte",
        away_team_id="doosan",
        stadium_id="sajik",
        game_start_at=(
            game_start_at
            or datetime(
                2026,
                8,
                15,
                9,
                0,
                tzinfo=timezone.utc,
            )
        ),
        status=GameStatus.SCHEDULED,
        home_score=None,
        away_score=None,
        result_text=None,
        created_at=now,
        updated_at=now,
    )


def create_request(
    *,
    game_id: str = GAME_ID,
    trip_start_at: datetime | None = None,
    trip_end_at: datetime | None = None,
) -> TripCreateRequest:
    return TripCreateRequest(
        game_id=game_id,
        title="두산 부산 원정",
        trip_start_at=(
            trip_start_at
            or datetime(
                2026,
                8,
                14,
                1,
                0,
                tzinfo=timezone.utc,
            )
        ),
        trip_end_at=(
            trip_end_at
            or datetime(
                2026,
                8,
                16,
                10,
                0,
                tzinfo=timezone.utc,
            )
        ),
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
        accommodation=None,
    )


def create_service(
    *,
    games: list[GameRecord] | None = None,
) -> tuple[TripService, StubTripRepository]:
    trip_repository = StubTripRepository()
    place_selection_repository = (
        StubPlaceSelectionRepository()
    )
    itinerary_plan_repository = (
        StubItineraryPlanRepository()
    )

    service = TripService(
        trip_repository=trip_repository,
        game_repository=StubGameRepository(
            games if games is not None else [create_game()]
        ),
        place_selection_repository=(
            place_selection_repository
        ),
        itinerary_plan_repository=(
            itinerary_plan_repository
        ),
    )

    service._test_place_selection_repository = (
        place_selection_repository
    )
    service._test_itinerary_plan_repository = (
        itinerary_plan_repository
    )

    return service, trip_repository


def test_create_trip_saves_owner_and_initial_status() -> None:
    service, _ = create_service()

    trip = service.create_trip(
        user_id="user-001",
        request=create_request(),
        idempotency_key="test-request-key",
    )

    assert trip.trip_id == "trip_auto_001"
    assert trip.user_id == "user-001"
    assert trip.game_id == GAME_ID
    assert trip.status.value == "PLANNING"
    assert trip.active_plan_id is None


def test_create_trip_rejects_missing_game() -> None:
    service, _ = create_service(games=[])

    with pytest.raises(AppException) as exception_info:
        service.create_trip(
            user_id="user-001",
            request=create_request(),
            idempotency_key="test-request-key",
        )

    exception = exception_info.value

    assert exception.status_code == 404
    assert exception.code == "GAME_NOT_FOUND"


def test_create_trip_rejects_game_outside_period() -> None:
    service, _ = create_service()

    request = create_request(
        trip_end_at=datetime(
            2026,
            8,
            15,
            8,
            59,
            tzinfo=timezone.utc,
        ),
    )

    with pytest.raises(AppException) as exception_info:
        service.create_trip(
            user_id="user-001",
            request=request,
            idempotency_key="test-request-key",
        )

    exception = exception_info.value

    assert exception.status_code == 400
    assert exception.code == "GAME_OUTSIDE_TRIP_PERIOD"


def test_get_my_trips_returns_only_owner_trips() -> None:
    service, repository = create_service()

    service.create_trip(
        user_id="user-001",
        request=create_request(),
        idempotency_key="test-request-key",
    )

    other_trip = TripDocument(
        user_id="user-002",
        game_id=GAME_ID,
        title="다른 사용자 여행",
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
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    repository.create(other_trip)

    trips = service.get_my_trips(
        user_id="user-001"
    )

    assert len(trips) == 1
    assert trips[0].user_id == "user-001"


def test_get_trip_rejects_other_owner() -> None:
    service, _ = create_service()

    trip = service.create_trip(
        user_id="user-001",
        request=create_request(),
        idempotency_key="test-request-key",
    )

    with pytest.raises(AppException) as exception_info:
        service.get_trip(
            user_id="user-002",
            trip_id=trip.trip_id,
        )

    exception = exception_info.value

    assert exception.status_code == 403
    assert exception.code == "TRIP_ACCESS_DENIED"


def test_get_missing_trip_raises_not_found() -> None:
    service, _ = create_service()

    with pytest.raises(AppException) as exception_info:
        service.get_trip(
            user_id="user-001",
            trip_id="missing",
        )

    exception = exception_info.value

    assert exception.status_code == 404
    assert exception.code == "TRIP_NOT_FOUND"


def test_update_trip_changes_provided_fields() -> None:
    service, _ = create_service()

    trip = service.create_trip(
        user_id="user-001",
        request=create_request(),
        idempotency_key="test-request-key",
    )

    updated = service.update_trip(
        user_id="user-001",
        trip_id=trip.trip_id,
        request=TripUpdateRequest(
            title="수정된 부산 원정",
            accommodation=None,
        ),
    )

    assert updated.title == "수정된 부산 원정"
    assert updated.game_id == GAME_ID
    assert updated.trip_start_at == trip.trip_start_at


def test_update_trip_validates_merged_period() -> None:
    service, _ = create_service()

    trip = service.create_trip(
        user_id="user-001",
        request=create_request(),
        idempotency_key="test-request-key",
    )

    with pytest.raises(AppException) as exception_info:
        service.update_trip(
            user_id="user-001",
            trip_id=trip.trip_id,
            request=TripUpdateRequest(
                trip_start_at=datetime(
                    2026,
                    8,
                    17,
                    tzinfo=timezone.utc,
                ),
            ),
        )

    exception = exception_info.value

    assert exception.status_code == 400
    assert exception.code == "TRIP_TIME_INVALID"


def test_update_trip_validates_game_in_new_period() -> None:
    service, _ = create_service()

    trip = service.create_trip(
        user_id="user-001",
        request=create_request(),
        idempotency_key="test-request-key",
    )

    with pytest.raises(AppException) as exception_info:
        service.update_trip(
            user_id="user-001",
            trip_id=trip.trip_id,
            request=TripUpdateRequest(
                trip_start_at=datetime(
                    2026,
                    8,
                    15,
                    9,
                    1,
                    tzinfo=timezone.utc,
                ),
            ),
        )

    exception = exception_info.value

    assert exception.status_code == 400
    assert exception.code == "GAME_OUTSIDE_TRIP_PERIOD"


def test_delete_trip_checks_owner_and_deletes() -> None:
    service, repository = create_service()

    trip = service.create_trip(
        user_id="user-001",
        request=create_request(),
        idempotency_key="test-request-key",
    )

    service.delete_trip(
        user_id="user-001",
        trip_id=trip.trip_id,
    )

    assert repository.get_by_id(trip.trip_id) is None
    assert (
        service._test_place_selection_repository.deleted_trip_ids
        == [trip.trip_id]
    )
    assert (
        service._test_itinerary_plan_repository.deleted_trip_ids
        == [trip.trip_id]
    )


def test_create_trip_translates_idempotency_conflict() -> None:
    service, repository = create_service()

    def raise_conflict(
        *,
        trip: TripDocument,
        idempotency_key: str,
    ) -> TripRecord:
        raise TripIdempotencyConflictError()

    repository.create_idempotent = raise_conflict

    with pytest.raises(AppException) as captured:
        service.create_trip(
            user_id="user-001",
            request=create_request(),
            idempotency_key="duplicate-request-key",
        )

    assert captured.value.status_code == 409
    assert captured.value.code == "TRIP_IDEMPOTENCY_CONFLICT"


def test_delete_trip_keeps_trip_when_child_cleanup_fails() -> None:
    service, repository = create_service()

    trip = service.create_trip(
        user_id="user-001",
        request=create_request(),
        idempotency_key="delete-failure-key",
    )

    def fail_delete_all(
        *,
        trip_id: str,
    ) -> int:
        raise RuntimeError("child cleanup failed")

    service._test_place_selection_repository.delete_all = (
        fail_delete_all
    )

    with pytest.raises(RuntimeError):
        service.delete_trip(
            user_id="user-001",
            trip_id=trip.trip_id,
        )

    assert repository.get_by_id(trip.trip_id) is not None

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from app.core.exceptions import AppException
from app.schemas.itinerary_plan import (
    ItineraryPlanRecord,
    ItineraryPlanStatus,
)
from app.schemas.trip import TripRecord, TripStatus
from app.services.itinerary_plan_service import (
    ItineraryPlanService,
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


def make_trip(
    *,
    user_id: str = USER_ID,
    active_plan_id: str | None = PLAN_ID,
    trip_status: TripStatus = TripStatus.GENERATED,
) -> TripRecord:
    return TripRecord(
        trip_id=TRIP_ID,
        user_id=user_id,
        game_id="game_001",
        title="부산 직관 여행",
        trip_start_at="2026-08-15T12:00:00+09:00",
        trip_end_at="2026-08-15T23:00:00+09:00",
        arrival_point={
            "name": "부산역",
            "latitude": 35.1151,
            "longitude": 129.0414,
        },
        departure_point={
            "name": "부산역",
            "latitude": 35.1151,
            "longitude": 129.0414,
        },
        accommodation=None,
        status=trip_status,
        active_plan_id=active_plan_id,
        created_at=NOW,
        updated_at=NOW,
    )


def make_plan(
    *,
    user_id: str = USER_ID,
    trip_id: str = TRIP_ID,
) -> ItineraryPlanRecord:
    return ItineraryPlanRecord(
        plan_id=PLAN_ID,
        trip_id=trip_id,
        user_id=user_id,
        status=ItineraryPlanStatus.ACTIVE,
        algorithm_version="greedy-anchor-v0.1",
        total_travel_minutes=0,
        days=[],
        excluded_places=[],
        created_at=NOW,
        updated_at=NOW,
    )


def make_service(
    *,
    trip=None,
    plan=None,
):
    trip_repository = Mock()
    trip_repository.get_by_id.return_value = (
        trip if trip is not None else make_trip()
    )

    plan_repository = Mock()
    plan_repository.get_by_id.return_value = (
        plan if plan is not None else make_plan()
    )

    service = ItineraryPlanService(
        trip_repository=trip_repository,
        itinerary_plan_repository=plan_repository,
    )

    return service, trip_repository, plan_repository


def test_get_active_plan_returns_plan() -> None:
    service, _, plan_repository = make_service()

    result = service.get_active_plan(
        user_id=USER_ID,
        trip_id=TRIP_ID,
    )

    assert result.plan_id == PLAN_ID
    assert result.trip_id == TRIP_ID

    plan_repository.get_by_id.assert_called_once_with(
        PLAN_ID
    )


def test_get_active_plan_rejects_missing_trip() -> None:
    service, trip_repository, _ = make_service()
    trip_repository.get_by_id.return_value = None

    with pytest.raises(AppException) as captured:
        service.get_active_plan(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.status_code == 404
    assert captured.value.code == "TRIP_NOT_FOUND"


def test_get_active_plan_rejects_other_user() -> None:
    service, _, _ = make_service(
        trip=make_trip(
            user_id="another-user",
        )
    )

    with pytest.raises(AppException) as captured:
        service.get_active_plan(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.status_code == 403
    assert captured.value.code == "TRIP_ACCESS_DENIED"


def test_get_active_plan_rejects_missing_active_plan_id() -> None:
    service, _, plan_repository = make_service(
        trip=make_trip(
            active_plan_id=None,
            trip_status=TripStatus.PLANNING,
        )
    )

    with pytest.raises(AppException) as captured:
        service.get_active_plan(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.status_code == 404
    assert captured.value.code == (
        "ITINERARY_PLAN_NOT_FOUND"
    )

    plan_repository.get_by_id.assert_not_called()


def test_get_active_plan_rejects_missing_plan_document() -> None:
    service, _, plan_repository = make_service()
    plan_repository.get_by_id.return_value = None

    with pytest.raises(AppException) as captured:
        service.get_active_plan(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.code == (
        "ITINERARY_PLAN_NOT_FOUND"
    )


def test_delete_active_plan_calls_repository() -> None:
    service, _, plan_repository = make_service()

    service.delete_active_plan(
        user_id=USER_ID,
        trip_id=TRIP_ID,
    )

    plan_repository.delete_active_plan.assert_called_once()

    arguments = (
        plan_repository
        .delete_active_plan
        .call_args.kwargs
    )

    assert arguments["trip_id"] == TRIP_ID
    assert arguments["plan_id"] == PLAN_ID
    assert arguments["updated_at"].tzinfo is not None


def test_delete_active_plan_rejects_generation_in_progress() -> None:
    service, _, plan_repository = make_service(
        trip=make_trip(
            trip_status=TripStatus.GENERATING,
        )
    )

    with pytest.raises(AppException) as captured:
        service.delete_active_plan(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.status_code == 409
    assert captured.value.code == (
        "TRIP_GENERATION_IN_PROGRESS"
    )

    plan_repository.delete_active_plan.assert_not_called()

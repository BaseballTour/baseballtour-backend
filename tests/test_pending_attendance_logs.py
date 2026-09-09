from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from app.schemas.itinerary_plan import ItineraryPlanStatus
from app.schemas.trip import TripRecord, TripStatus
from app.services.attendance_log_service import (
    AttendanceLogService,
)


USER_ID = "firebase-user-123"


def make_trip(
    *,
    trip_id: str,
    end_year: int = 2020,
    status: TripStatus = TripStatus.GENERATED,
    active_plan_id: str | None = "plan_001",
) -> TripRecord:
    return TripRecord.model_construct(
        trip_id=trip_id,
        user_id=USER_ID,
        game_id="game_001",
        title=f"{trip_id} 원정",
        trip_end_at=datetime(
            end_year,
            8,
            15,
            14,
            0,
            tzinfo=timezone.utc,
        ),
        status=status,
        active_plan_id=active_plan_id,
    )


def make_service(
    *,
    trips,
    logged_trip_ids=(),
    plan_status=ItineraryPlanStatus.ACTIVE,
):
    trip_repository = Mock()
    trip_repository.get_by_user_id.return_value = trips

    attendance_log_repository = Mock()
    attendance_log_repository.get_by_user_id.return_value = [
        SimpleNamespace(trip_id=trip_id)
        for trip_id in logged_trip_ids
    ]

    itinerary_plan_repository = Mock()
    if plan_status is None:
        itinerary_plan_repository.get_by_id.return_value = None
    else:
        itinerary_plan_repository.get_by_id.return_value = (
            SimpleNamespace(status=plan_status)
        )

    service = AttendanceLogService(
        trip_repository=trip_repository,
        game_repository=Mock(),
        itinerary_plan_repository=(
            itinerary_plan_repository
        ),
        attendance_log_repository=(
            attendance_log_repository
        ),
        log_entry_repository=Mock(),
    )

    return (
        service,
        trip_repository,
        attendance_log_repository,
    )


def test_pending_trip_is_returned() -> None:
    trip = make_trip(trip_id="trip_pending")
    service, trip_repository, log_repository = (
        make_service(trips=[trip])
    )

    response = service.get_pending_attendance_log_trips(
        user_id=USER_ID
    )

    assert response.attendance_log_required is True
    assert len(response.trips) == 1
    assert response.trips[0].trip_id == "trip_pending"
    assert response.trips[0].title == "trip_pending 원정"

    trip_repository.get_by_user_id.assert_called_once_with(
        USER_ID
    )
    log_repository.get_by_user_id.assert_called_once_with(
        USER_ID
    )


def test_existing_log_excludes_trip() -> None:
    trip = make_trip(trip_id="trip_logged")
    service, _, _ = make_service(
        trips=[trip],
        logged_trip_ids=["trip_logged"],
    )

    response = service.get_pending_attendance_log_trips(
        user_id=USER_ID
    )

    assert response.attendance_log_required is False
    assert response.trips == []


def test_future_trip_is_excluded() -> None:
    trip = make_trip(
        trip_id="trip_future",
        end_year=2999,
    )
    service, _, _ = make_service(trips=[trip])

    response = service.get_pending_attendance_log_trips(
        user_id=USER_ID
    )

    assert response.attendance_log_required is False
    assert response.trips == []


def test_cancelled_trip_is_excluded() -> None:
    trip = make_trip(
        trip_id="trip_cancelled",
        status=TripStatus.CANCELLED,
    )
    service, _, _ = make_service(trips=[trip])

    response = service.get_pending_attendance_log_trips(
        user_id=USER_ID
    )

    assert response.attendance_log_required is False
    assert response.trips == []


def test_trip_without_active_plan_is_excluded() -> None:
    trip = make_trip(
        trip_id="trip_without_plan",
        active_plan_id=None,
    )
    service, _, _ = make_service(trips=[trip])

    response = service.get_pending_attendance_log_trips(
        user_id=USER_ID
    )

    assert response.attendance_log_required is False
    assert response.trips == []


def test_pending_trips_are_sorted_by_recent_end_time() -> None:
    older = make_trip(trip_id="trip_old")
    newer = older.model_copy(
        update={
            "trip_id": "trip_new",
            "title": "trip_new 원정",
            "trip_end_at": datetime(
                2021,
                8,
                15,
                14,
                0,
                tzinfo=timezone.utc,
            ),
        }
    )

    service, _, _ = make_service(
        trips=[older, newer]
    )

    response = service.get_pending_attendance_log_trips(
        user_id=USER_ID
    )

    assert [
        trip.trip_id
        for trip in response.trips
    ] == [
        "trip_new",
        "trip_old",
    ]


def test_response_uses_camel_case_contract() -> None:
    service, _, _ = make_service(
        trips=[make_trip(trip_id="trip_pending")]
    )

    response = service.get_pending_attendance_log_trips(
        user_id=USER_ID
    )

    payload = response.model_dump(
        mode="json",
        by_alias=True,
    )

    assert payload["attendanceLogRequired"] is True
    assert payload["trips"][0]["tripId"] == "trip_pending"
    assert "tripEndAt" in payload["trips"][0]



def test_missing_active_plan_record_is_excluded() -> None:
    trip = make_trip(trip_id="trip_missing_plan")

    service, _, _ = make_service(
        trips=[trip],
        plan_status=None,
    )

    response = service.get_pending_attendance_log_trips(
        user_id=USER_ID
    )

    assert response.attendance_log_required is False
    assert response.trips == []


def test_archived_plan_is_excluded() -> None:
    trip = make_trip(trip_id="trip_archived_plan")

    service, _, _ = make_service(
        trips=[trip],
        plan_status=ItineraryPlanStatus.ARCHIVED,
    )

    response = service.get_pending_attendance_log_trips(
        user_id=USER_ID
    )

    assert response.attendance_log_required is False
    assert response.trips == []


def test_pending_trip_uses_korean_date_boundary(
    monkeypatch,
) -> None:
    trip = make_trip(
        trip_id="trip_boundary",
        end_year=2026,
    )

    service, _, _ = make_service(trips=[trip])

    original_datetime = datetime

    class FrozenDateTime(original_datetime):
        frozen_now = original_datetime(
            2026,
            8,
            15,
            14,
            59,
            59,
            tzinfo=timezone.utc,
        )

        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return cls.frozen_now.replace(
                    tzinfo=None
                )
            return cls.frozen_now.astimezone(tz)

    monkeypatch.setattr(
        "app.services.attendance_log_service.datetime",
        FrozenDateTime,
    )

    # 2026-08-15 23:59:59 KST:
    # 여행 종료일 당일이므로 아직 대상이 아닙니다.
    before_midnight = (
        service.get_pending_attendance_log_trips(
            user_id=USER_ID
        )
    )

    assert (
        before_midnight.attendance_log_required
        is False
    )
    assert before_midnight.trips == []

    # 2026-08-16 00:00:00 KST:
    # 여행 종료 다음 날이므로 즉시 대상이 됩니다.
    FrozenDateTime.frozen_now = original_datetime(
        2026,
        8,
        15,
        15,
        0,
        0,
        tzinfo=timezone.utc,
    )

    after_midnight = (
        service.get_pending_attendance_log_trips(
            user_id=USER_ID
        )
    )

    assert (
        after_midnight.attendance_log_required
        is True
    )
    assert [
        item.trip_id
        for item in after_midnight.trips
    ] == ["trip_boundary"]

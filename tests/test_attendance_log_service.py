from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.exceptions import AppException
from app.schemas.attendance_log import (
    AttendanceLogRecord,
    AttendanceLogStatus,
    LogEntryType,
)
from app.schemas.itinerary_plan import (
    ItineraryPlanRecord,
    ItineraryPlanStatus,
)
from app.schemas.trip import (
    TripRecord,
    TripStatus,
)
from app.services.attendance_log_service import (
    AttendanceLogService,
)


USER_ID = "firebase-user-123"
TRIP_ID = "trip_001"
PLAN_ID = "plan_001"
GAME_ID = "game_001"

NOW = datetime(
    2026,
    8,
    19,
    3,
    0,
    tzinfo=timezone.utc,
)


def make_trip(
    *,
    user_id: str = USER_ID,
    active_plan_id: str | None = PLAN_ID,
) -> TripRecord:
    return TripRecord(
        trip_id=TRIP_ID,
        user_id=user_id,
        game_id=GAME_ID,
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
        status=TripStatus.GENERATED,
        active_plan_id=active_plan_id,
        created_at=NOW,
        updated_at=NOW,
    )


def make_plan(
    *,
    status: ItineraryPlanStatus = (
        ItineraryPlanStatus.ACTIVE
    ),
) -> ItineraryPlanRecord:
    return ItineraryPlanRecord(
        plan_id=PLAN_ID,
        trip_id=TRIP_ID,
        user_id=USER_ID,
        status=status,
        algorithm_version="auto-fill-v0.4",
        total_travel_minutes=0,
        days=[
            {
                "date": "2026-08-15",
                "dayType": "GAME_DAY",
                "items": [
                    {
                        "itemId": "arrival",
                        "type": "ARRIVAL_POINT",
                        "sequence": 1,
                        "name": "부산역",
                        "address": "부산역",
                        "latitude": 35.1151,
                        "longitude": 129.0414,
                        "scheduledStartAt": (
                            "2026-08-15T12:00:00+09:00"
                        ),
                        "scheduledEndAt": (
                            "2026-08-15T12:20:00+09:00"
                        ),
                        "travelMinutesFromPrevious": 0,
                        "isRequired": True,
                    },
                    {
                        "itemId": "place_1",
                        "type": "PLACE",
                        "sequence": 2,
                        "placeId": "tour_001",
                        "name": "광안리해수욕장",
                        "address": "부산광역시 수영구",
                        "latitude": 35.1532,
                        "longitude": 129.1187,
                        "scheduledStartAt": (
                            "2026-08-15T14:00:00+09:00"
                        ),
                        "scheduledEndAt": (
                            "2026-08-15T15:30:00+09:00"
                        ),
                        "travelMinutesFromPrevious": 0,
                        "isRequired": True,
                    },
                    {
                        "itemId": "stadium",
                        "type": "STADIUM",
                        "sequence": 3,
                        "placeId": "sajik",
                        "name": "사직야구장",
                        "address": (
                            "부산광역시 동래구 사직로 45"
                        ),
                        "latitude": 35.194,
                        "longitude": 129.0615,
                        "scheduledStartAt": (
                            "2026-08-15T17:20:00+09:00"
                        ),
                        "scheduledEndAt": (
                            "2026-08-15T21:00:00+09:00"
                        ),
                        "travelMinutesFromPrevious": 0,
                        "isRequired": True,
                    },
                    {
                        "itemId": "departure",
                        "type": "DEPARTURE_POINT",
                        "sequence": 4,
                        "name": "부산역",
                        "address": "부산역",
                        "latitude": 35.1151,
                        "longitude": 129.0414,
                        "scheduledStartAt": (
                            "2026-08-15T22:00:00+09:00"
                        ),
                        "scheduledEndAt": (
                            "2026-08-15T22:20:00+09:00"
                        ),
                        "travelMinutesFromPrevious": 0,
                        "isRequired": True,
                    },
                ],
            }
        ],
        excluded_places=[],
        created_at=NOW,
        updated_at=NOW,
    )


def make_service(
    *,
    trip=None,
    plan=None,
    existing_log=None,
    game=None,
):
    trip_repository = Mock()
    trip_repository.get_by_id.return_value = (
        trip
        if trip is not None
        else make_trip()
    )

    game_repository = Mock()
    game_repository.get_by_id.return_value = (
        game
        if game is not None
        else SimpleNamespace(
            game_id=GAME_ID,
        )
    )

    plan_repository = Mock()
    plan_repository.get_by_id.return_value = (
        plan
        if plan is not None
        else make_plan()
    )

    attendance_log_repository = Mock()
    attendance_log_repository.get_active_by_trip_id.return_value = (
        existing_log
    )

    def create_log(document):
        return AttendanceLogRecord(
            attendance_log_id="log_001",
            **document.model_dump(),
        )

    attendance_log_repository.create.side_effect = (
        create_log
    )

    log_entry_repository = Mock()

    service = AttendanceLogService(
        trip_repository=trip_repository,
        game_repository=game_repository,
        itinerary_plan_repository=plan_repository,
        attendance_log_repository=(
            attendance_log_repository
        ),
        log_entry_repository=log_entry_repository,
    )

    return SimpleNamespace(
        service=service,
        trip_repository=trip_repository,
        game_repository=game_repository,
        plan_repository=plan_repository,
        attendance_log_repository=(
            attendance_log_repository
        ),
        log_entry_repository=log_entry_repository,
    )


def test_create_draft_creates_log_and_entries() -> None:
    context = make_service()

    result = context.service.create_draft(
        user_id=USER_ID,
        trip_id=TRIP_ID,
    )

    assert result.attendance_log_id == "log_001"
    assert result.user_id == USER_ID
    assert result.trip_id == TRIP_ID
    assert result.game_id == GAME_ID
    assert result.plan_id == PLAN_ID
    assert result.log_title == "부산 직관 여행"
    assert (
        result.log_status
        == AttendanceLogStatus.DRAFT
    )

    context.attendance_log_repository.create.assert_called_once()

    log_document = (
        context.attendance_log_repository
        .create.call_args.args[0]
    )

    assert log_document.user_id == USER_ID
    assert log_document.trip_id == TRIP_ID
    assert log_document.game_id == GAME_ID
    assert log_document.plan_id == PLAN_ID
    assert (
        log_document.log_status
        == AttendanceLogStatus.DRAFT
    )
    assert log_document.created_at.tzinfo is not None
    assert log_document.updated_at.tzinfo is not None

    assert (
        context.log_entry_repository
        .create.call_count
        == 2
    )

    first_call = (
        context.log_entry_repository
        .create.call_args_list[0]
    )

    assert first_call.args[0] == "log_001"

    first_entry = first_call.args[1]

    assert first_entry.plan_item_id == "place_1"
    assert first_entry.place_id == "tour_001"
    assert first_entry.sequence_no == 1
    assert first_entry.entry_type == LogEntryType.PLACE
    assert first_entry.entry_title == "광안리해수욕장"

    second_call = (
        context.log_entry_repository
        .create.call_args_list[1]
    )

    second_entry = second_call.args[1]

    assert second_entry.plan_item_id == "stadium"
    assert second_entry.place_id is None
    assert second_entry.sequence_no == 2
    assert second_entry.entry_type == LogEntryType.GAME
    assert second_entry.entry_title == "사직야구장"

    assert (
        first_entry.occurred_at.isoformat()
        == "2026-08-15T14:00:00+09:00"
    )
    assert (
        second_entry.occurred_at.isoformat()
        == "2026-08-15T17:20:00+09:00"
    )


def test_create_draft_rejects_missing_trip() -> None:
    context = make_service()
    context.trip_repository.get_by_id.return_value = None

    with pytest.raises(AppException) as captured:
        context.service.create_draft(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.status_code == 404
    assert captured.value.code == "TRIP_NOT_FOUND"

    context.attendance_log_repository.create.assert_not_called()


def test_create_draft_rejects_other_user() -> None:
    context = make_service(
        trip=make_trip(
            user_id="another-user",
        )
    )

    with pytest.raises(AppException) as captured:
        context.service.create_draft(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.status_code == 403
    assert captured.value.code == "TRIP_ACCESS_DENIED"

    context.attendance_log_repository.create.assert_not_called()


def test_create_draft_rejects_duplicate_log() -> None:
    existing = SimpleNamespace(
        attendance_log_id="log_existing",
    )

    context = make_service(
        existing_log=existing
    )

    with pytest.raises(AppException) as captured:
        context.service.create_draft(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.status_code == 409
    assert captured.value.code == (
        "ATTENDANCE_LOG_ALREADY_EXISTS"
    )

    context.plan_repository.get_by_id.assert_not_called()
    context.attendance_log_repository.create.assert_not_called()


def test_create_draft_requires_active_plan_id() -> None:
    context = make_service(
        trip=make_trip(
            active_plan_id=None,
        )
    )

    with pytest.raises(AppException) as captured:
        context.service.create_draft(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.status_code == 404
    assert captured.value.code == (
        "ITINERARY_PLAN_NOT_FOUND"
    )

    context.plan_repository.get_by_id.assert_not_called()
    context.attendance_log_repository.create.assert_not_called()


def test_create_draft_rejects_missing_plan() -> None:
    context = make_service()
    context.plan_repository.get_by_id.return_value = None

    with pytest.raises(AppException) as captured:
        context.service.create_draft(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.status_code == 404
    assert captured.value.code == (
        "ITINERARY_PLAN_NOT_FOUND"
    )

    context.attendance_log_repository.create.assert_not_called()


def test_create_draft_rejects_archived_plan() -> None:
    context = make_service(
        plan=make_plan(
            status=ItineraryPlanStatus.ARCHIVED,
        )
    )

    with pytest.raises(AppException) as captured:
        context.service.create_draft(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.status_code == 404
    assert captured.value.code == (
        "ITINERARY_PLAN_NOT_FOUND"
    )

    context.attendance_log_repository.create.assert_not_called()


def test_create_draft_rejects_missing_game() -> None:
    context = make_service()
    context.game_repository.get_by_id.return_value = None

    with pytest.raises(AppException) as captured:
        context.service.create_draft(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.status_code == 404
    assert captured.value.code == "GAME_NOT_FOUND"

    context.attendance_log_repository.create.assert_not_called()


def test_create_draft_skips_non_loggable_anchors() -> None:
    context = make_service()

    context.service.create_draft(
        user_id=USER_ID,
        trip_id=TRIP_ID,
    )

    entries = [
        call.args[1]
        for call in (
            context.log_entry_repository
            .create.call_args_list
        )
    ]

    assert len(entries) == 2

    assert {
        entry.entry_type
        for entry in entries
    } == {
        LogEntryType.PLACE,
        LogEntryType.GAME,
    }

    assert all(
        entry.plan_item_id
        not in {
            "arrival",
            "departure",
        }
        for entry in entries
    )

def make_attendance_log(
    *,
    user_id: str = USER_ID,
    trip_id: str = TRIP_ID,
    plan_id: str | None = PLAN_ID,
) -> AttendanceLogRecord:
    return AttendanceLogRecord(
        attendance_log_id="log_001",
        user_id=user_id,
        trip_id=trip_id,
        game_id=GAME_ID,
        plan_id=plan_id,
        log_title="부산 직관 여행",
        summary_text=None,
        log_status=AttendanceLogStatus.PUBLISHED,
        created_at=NOW,
        updated_at=NOW,
        deleted_at=None,
    )


def test_get_itinerary_returns_archived_plan() -> None:
    context = make_service(
        plan=make_plan(
            status=ItineraryPlanStatus.ARCHIVED,
        )
    )
    context.attendance_log_repository.get_by_id.return_value = (
        make_attendance_log()
    )

    result = context.service.get_itinerary(
        user_id=USER_ID,
        attendance_log_id="log_001",
    )

    assert result.plan_id == PLAN_ID
    assert result.trip_id == TRIP_ID
    assert result.status == ItineraryPlanStatus.ARCHIVED

    context.attendance_log_repository.get_by_id.assert_called_once_with(
        "log_001"
    )
    context.plan_repository.get_by_id.assert_called_once_with(
        PLAN_ID
    )


def test_get_itinerary_rejects_missing_log() -> None:
    context = make_service()
    context.attendance_log_repository.get_by_id.return_value = None

    with pytest.raises(AppException) as captured:
        context.service.get_itinerary(
            user_id=USER_ID,
            attendance_log_id="log_missing",
        )

    assert captured.value.status_code == 404
    assert captured.value.code == "ATTENDANCE_LOG_NOT_FOUND"
    context.plan_repository.get_by_id.assert_not_called()


def test_get_itinerary_rejects_other_user() -> None:
    context = make_service()
    context.attendance_log_repository.get_by_id.return_value = (
        make_attendance_log(
            user_id="another-user",
        )
    )

    with pytest.raises(AppException) as captured:
        context.service.get_itinerary(
            user_id=USER_ID,
            attendance_log_id="log_001",
        )

    assert captured.value.status_code == 403
    assert captured.value.code == "ATTENDANCE_LOG_ACCESS_DENIED"
    context.plan_repository.get_by_id.assert_not_called()


def test_get_itinerary_requires_plan_id() -> None:
    context = make_service()
    context.attendance_log_repository.get_by_id.return_value = (
        make_attendance_log(
            plan_id=None,
        )
    )

    with pytest.raises(AppException) as captured:
        context.service.get_itinerary(
            user_id=USER_ID,
            attendance_log_id="log_001",
        )

    assert captured.value.status_code == 404
    assert captured.value.code == "ITINERARY_PLAN_NOT_FOUND"
    context.plan_repository.get_by_id.assert_not_called()


def test_get_itinerary_rejects_missing_plan() -> None:
    context = make_service()
    context.attendance_log_repository.get_by_id.return_value = (
        make_attendance_log()
    )
    context.plan_repository.get_by_id.return_value = None

    with pytest.raises(AppException) as captured:
        context.service.get_itinerary(
            user_id=USER_ID,
            attendance_log_id="log_001",
        )

    assert captured.value.status_code == 404
    assert captured.value.code == "ITINERARY_PLAN_NOT_FOUND"
    context.plan_repository.get_by_id.assert_called_once_with(
        PLAN_ID
    )


def test_get_itinerary_rejects_plan_mismatch() -> None:
    mismatched_plan = make_plan().model_copy(
        update={
            "trip_id": "trip_other",
        }
    )

    context = make_service(
        plan=mismatched_plan,
    )
    context.attendance_log_repository.get_by_id.return_value = (
        make_attendance_log()
    )

    with pytest.raises(AppException) as captured:
        context.service.get_itinerary(
            user_id=USER_ID,
            attendance_log_id="log_001",
        )

    assert captured.value.status_code == 409
    assert captured.value.code == "ATTENDANCE_LOG_PLAN_MISMATCH"

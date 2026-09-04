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


def make_crud_service(
    *,
    log_user_id: str = USER_ID,
):
    from types import SimpleNamespace

    attendance_repository = Mock()
    attendance_repository.get_by_id.return_value = (
        make_attendance_log(
            user_id=log_user_id,
        )
    )

    log_entry_repository = Mock()
    log_media_repository = Mock()
    storage_service = Mock()

    service = AttendanceLogService(
        trip_repository=Mock(),
        game_repository=Mock(),
        itinerary_plan_repository=Mock(),
        attendance_log_repository=(
            attendance_repository
        ),
        log_entry_repository=(
            log_entry_repository
        ),
        log_media_repository=(
            log_media_repository
        ),
        storage_service=storage_service,
    )

    return SimpleNamespace(
        service=service,
        attendance_repository=(
            attendance_repository
        ),
        log_entry_repository=(
            log_entry_repository
        ),
        log_media_repository=(
            log_media_repository
        ),
        storage_service=storage_service,
    )


def test_update_log_checks_owner_and_updates_fields() -> None:
    from app.schemas.attendance_log import (
        AttendanceLogUpdateRequest,
    )

    context = make_crud_service()

    updated = make_attendance_log().model_copy(
        update={
            "log_title": "수정한 직관 로그",
        }
    )

    context.attendance_repository.update.return_value = (
        updated
    )

    result = context.service.update_log(
        user_id=USER_ID,
        attendance_log_id="log_001",
        request=AttendanceLogUpdateRequest(
            log_title="수정한 직관 로그",
        ),
    )

    assert result.log_title == "수정한 직관 로그"

    context.attendance_repository.get_by_id.assert_called_once_with(
        "log_001"
    )

    args = (
        context.attendance_repository
        .update.call_args.args
    )

    assert args[0] == "log_001"
    assert args[1]["logTitle"] == (
        "수정한 직관 로그"
    )
    assert "updatedAt" in args[1]


def test_update_log_rejects_other_owner() -> None:
    from app.schemas.attendance_log import (
        AttendanceLogUpdateRequest,
    )

    context = make_crud_service(
        log_user_id="another-user",
    )

    with pytest.raises(AppException) as captured:
        context.service.update_log(
            user_id=USER_ID,
            attendance_log_id="log_001",
            request=AttendanceLogUpdateRequest(
                log_title="수정",
            ),
        )

    assert captured.value.status_code == 403
    assert (
        captured.value.code
        == "ATTENDANCE_LOG_ACCESS_DENIED"
    )

    context.attendance_repository.update.assert_not_called()


def test_update_log_rejects_archived_status() -> None:
    from app.schemas.attendance_log import (
        AttendanceLogStatus,
        AttendanceLogUpdateRequest,
    )

    context = make_crud_service()

    with pytest.raises(AppException) as captured:
        context.service.update_log(
            user_id=USER_ID,
            attendance_log_id="log_001",
            request=AttendanceLogUpdateRequest(
                log_status=(
                    AttendanceLogStatus.ARCHIVED
                ),
            ),
        )

    assert captured.value.status_code == 400
    assert (
        captured.value.code
        == "ATTENDANCE_LOG_STATUS_INVALID"
    )


def test_delete_media_removes_storage_first() -> None:
    context = make_crud_service()

    context.log_entry_repository.get_by_id.return_value = (
        SimpleNamespace(
            log_entry_id="entry_001",
        )
    )

    context.log_media_repository.get_by_id.return_value = (
        SimpleNamespace(
            log_media_id="media_001",
            storage_path=(
                "users/firebase-user-123/"
                "attendance-logs/log_001/"
                "entry_001/media_001.jpg"
            ),
        )
    )

    context.log_media_repository.delete.return_value = True

    context.service.delete_media(
        user_id=USER_ID,
        attendance_log_id="log_001",
        log_entry_id="entry_001",
        log_media_id="media_001",
    )

    context.storage_service.delete_storage_path.assert_called_once_with(
        (
            "users/firebase-user-123/"
            "attendance-logs/log_001/"
            "entry_001/media_001.jpg"
        )
    )

    context.log_media_repository.delete.assert_called_once_with(
        "log_001",
        "entry_001",
        "media_001",
    )


def test_delete_entry_cleans_media_and_entry() -> None:
    context = make_crud_service()

    context.log_entry_repository.get_by_id.return_value = (
        SimpleNamespace(
            log_entry_id="entry_001",
        )
    )

    context.log_media_repository.get_all.return_value = [
        SimpleNamespace(
            log_media_id="media_001",
            storage_path=(
                "users/firebase-user-123/"
                "attendance-logs/log_001/"
                "entry_001/media_001.jpg"
            ),
        ),
        SimpleNamespace(
            log_media_id="media_legacy",
            storage_path=None,
        ),
    ]

    context.log_entry_repository.delete.return_value = True
    context.log_media_repository.delete.return_value = True

    context.service.delete_entry(
        user_id=USER_ID,
        attendance_log_id="log_001",
        log_entry_id="entry_001",
    )

    context.storage_service.delete_storage_path.assert_called_once()

    assert (
        context.log_media_repository.delete.call_count
        == 2
    )

    context.log_entry_repository.delete.assert_called_once_with(
        "log_001",
        "entry_001",
    )


def test_delete_log_cleans_entries_before_soft_delete() -> None:
    context = make_crud_service()

    context.log_entry_repository.get_all.return_value = [
        SimpleNamespace(
            log_entry_id="entry_001",
        ),
        SimpleNamespace(
            log_entry_id="entry_002",
        ),
    ]

    context.log_media_repository.get_all.return_value = []
    context.log_entry_repository.delete.return_value = True
    context.attendance_repository.soft_delete.return_value = True

    context.service.delete_log(
        user_id=USER_ID,
        attendance_log_id="log_001",
    )

    assert (
        context.log_entry_repository.delete.call_count
        == 2
    )

    context.attendance_repository.soft_delete.assert_called_once()

    args = (
        context.attendance_repository
        .soft_delete.call_args
    )

    assert args.args[0] == "log_001"
    assert "deleted_at" in args.kwargs


def test_get_detail_allows_public_log_for_other_user() -> None:
    from app.schemas.attendance_log import (
        AttendanceLogVisibility,
    )

    context = make_crud_service(
        log_user_id="another-user",
    )

    public_log = make_attendance_log(
        user_id="another-user",
    ).model_copy(
        update={
            "visibility": (
                AttendanceLogVisibility.PUBLIC
            ),
        }
    )

    context.attendance_repository.get_by_id.return_value = (
        public_log
    )

    context.log_entry_repository.get_all.return_value = []

    result = context.service.get_detail(
        user_id=USER_ID,
        attendance_log_id="log_001",
    )

    assert (
        result.visibility
        == AttendanceLogVisibility.PUBLIC
    )


def test_get_detail_rejects_private_log_for_other_user() -> None:
    from app.schemas.attendance_log import (
        AttendanceLogVisibility,
    )

    context = make_crud_service(
        log_user_id="another-user",
    )

    private_log = make_attendance_log(
        user_id="another-user",
    ).model_copy(
        update={
            "visibility": (
                AttendanceLogVisibility.PRIVATE
            ),
        }
    )

    context.attendance_repository.get_by_id.return_value = (
        private_log
    )

    with pytest.raises(AppException) as captured:
        context.service.get_detail(
            user_id=USER_ID,
            attendance_log_id="log_001",
        )

    assert captured.value.status_code == 403

    assert (
        captured.value.code
        == "ATTENDANCE_LOG_ACCESS_DENIED"
    )

    context.log_entry_repository.get_all.assert_not_called()


def test_update_log_changes_visibility() -> None:
    from app.schemas.attendance_log import (
        AttendanceLogUpdateRequest,
        AttendanceLogVisibility,
    )

    context = make_crud_service()

    updated = make_attendance_log().model_copy(
        update={
            "visibility": (
                AttendanceLogVisibility.PUBLIC
            ),
        }
    )

    context.attendance_repository.update.return_value = (
        updated
    )

    result = context.service.update_log(
        user_id=USER_ID,
        attendance_log_id="log_001",
        request=AttendanceLogUpdateRequest(
            visibility=(
                AttendanceLogVisibility.PUBLIC
            ),
        ),
    )

    assert (
        result.visibility
        == AttendanceLogVisibility.PUBLIC
    )

    updates = (
        context.attendance_repository
        .update.call_args.args[1]
    )

    assert updates["visibility"] == "PUBLIC"


def test_public_log_itinerary_still_rejects_other_user() -> None:
    from app.schemas.attendance_log import (
        AttendanceLogVisibility,
    )

    context = make_service()

    public_log = make_attendance_log(
        user_id="another-user",
    ).model_copy(
        update={
            "visibility": (
                AttendanceLogVisibility.PUBLIC
            ),
        }
    )

    context.attendance_log_repository.get_by_id.return_value = (
        public_log
    )

    with pytest.raises(AppException) as captured:
        context.service.get_itinerary(
            user_id=USER_ID,
            attendance_log_id="log_001",
        )

    assert captured.value.status_code == 403

    assert (
        captured.value.code
        == "ATTENDANCE_LOG_ACCESS_DENIED"
    )

    context.plan_repository.get_by_id.assert_not_called()


def make_archive_service(
    *,
    records=None,
    support_team_id="doosan",
    game=None,
    entries=None,
    media_by_entry=None,
):
    from app.schemas.attendance_log import LogMediaType

    attendance_repository = Mock()
    attendance_repository.get_by_user_id.return_value = (
        records or []
    )

    user_repository = Mock()
    user_repository.get_by_id.return_value = (
        SimpleNamespace(
            support_team_id=support_team_id,
        )
    )

    game_service = Mock()
    game_service.get_game.return_value = (
        game
        or SimpleNamespace(
            game_start_at=NOW,
            stadium=SimpleNamespace(
                name="사직야구장",
            ),
            home_team=SimpleNamespace(
                team_id="lotte",
                name="롯데 자이언츠",
            ),
            away_team=SimpleNamespace(
                team_id="doosan",
                name="두산 베어스",
            ),
            home_score=3,
            away_score=5,
        )
    )

    log_entry_repository = Mock()
    log_entry_repository.get_all.return_value = (
        entries or []
    )

    log_media_repository = Mock()

    media_by_entry = media_by_entry or {}

    def get_media(
        attendance_log_id,
        log_entry_id,
    ):
        return media_by_entry.get(
            log_entry_id,
            [],
        )

    log_media_repository.get_all.side_effect = get_media

    storage_service = Mock()
    storage_service.create_download_url.side_effect = (
        lambda path: f"https://signed.example/{path}"
    )

    service = AttendanceLogService(
        attendance_log_repository=(
            attendance_repository
        ),
        log_entry_repository=(
            log_entry_repository
        ),
        log_media_repository=(
            log_media_repository
        ),
        storage_service=storage_service,
        user_repository=user_repository,
        game_service=game_service,
    )

    return SimpleNamespace(
        service=service,
        attendance_repository=(
            attendance_repository
        ),
        user_repository=user_repository,
        game_service=game_service,
        log_entry_repository=(
            log_entry_repository
        ),
        log_media_repository=(
            log_media_repository
        ),
        storage_service=storage_service,
        LogMediaType=LogMediaType,
    )


def make_archive_record(
    *,
    attendance_log_id="log_001",
    created_at=NOW,
):
    from app.schemas.attendance_log import (
        AttendanceLogVisibility,
    )

    return AttendanceLogRecord(
        attendance_log_id=attendance_log_id,
        user_id=USER_ID,
        trip_id=TRIP_ID,
        game_id=GAME_ID,
        plan_id=PLAN_ID,
        log_title="부산 직관 여행",
        summary_text="역전승 직관",
        log_status=AttendanceLogStatus.PUBLISHED,
        visibility=AttendanceLogVisibility.PRIVATE,
        created_at=created_at,
        updated_at=created_at,
        deleted_at=None,
    )


def test_archive_log_resolves_away_win() -> None:
    from app.schemas.attendance_log import (
        AttendanceLogGameResult,
        AttendanceLogHomeSide,
    )

    context = make_archive_service(
        records=[make_archive_record()],
        support_team_id="doosan",
    )

    data, next_page_token = (
        context.service.list_archive_logs(
            user_id=USER_ID,
            page_size=12,
        )
    )

    assert len(data) == 1
    assert next_page_token is None

    item = data[0]

    assert item.stadium_name == "사직야구장"
    assert item.home_team_name == "롯데 자이언츠"
    assert item.away_team_name == "두산 베어스"
    assert item.home_score == 3
    assert item.away_score == 5

    assert (
        item.home_side
        == AttendanceLogHomeSide.AWAY
    )
    assert (
        item.result
        == AttendanceLogGameResult.WIN
    )


@pytest.mark.parametrize(
    (
        "support_team_id",
        "home_score",
        "away_score",
        "expected_side",
        "expected_result",
    ),
    [
        ("lotte", 5, 3, "HOME", "WIN"),
        ("lotte", 3, 5, "HOME", "LOSS"),
        ("doosan", 3, 5, "AWAY", "WIN"),
        ("doosan", 5, 3, "AWAY", "LOSS"),
        ("doosan", 4, 4, "AWAY", "DRAW"),
        ("lg", 5, 3, "OTHER", None),
        ("lotte", None, None, "HOME", None),
    ],
)
def test_archive_log_result_matrix(
    support_team_id,
    home_score,
    away_score,
    expected_side,
    expected_result,
) -> None:
    game = SimpleNamespace(
        game_start_at=NOW,
        stadium=SimpleNamespace(
            name="사직야구장",
        ),
        home_team=SimpleNamespace(
            team_id="lotte",
            name="롯데 자이언츠",
        ),
        away_team=SimpleNamespace(
            team_id="doosan",
            name="두산 베어스",
        ),
        home_score=home_score,
        away_score=away_score,
    )

    context = make_archive_service(
        records=[make_archive_record()],
        support_team_id=support_team_id,
        game=game,
    )

    data, _ = context.service.list_archive_logs(
        user_id=USER_ID,
    )

    item = data[0]

    assert item.home_side.value == expected_side

    if expected_result is None:
        assert item.result is None
    else:
        assert item.result.value == expected_result


def test_archive_log_uses_first_image_as_cover() -> None:
    context = make_archive_service(
        records=[make_archive_record()],
        entries=[
            SimpleNamespace(
                log_entry_id="entry_001",
            ),
            SimpleNamespace(
                log_entry_id="entry_002",
            ),
        ],
    )

    context.log_media_repository.get_all.side_effect = (
        lambda attendance_log_id, entry_id: {
            "entry_001": [
                SimpleNamespace(
                    media_type=(
                        context.LogMediaType.VIDEO
                    ),
                    storage_path=(
                        "users/test/video.mp4"
                    ),
                    media_url=None,
                ),
            ],
            "entry_002": [
                SimpleNamespace(
                    media_type=(
                        context.LogMediaType.IMAGE
                    ),
                    storage_path=(
                        "users/test/photo.png"
                    ),
                    media_url=None,
                ),
            ],
        }.get(entry_id, [])
    )

    data, _ = context.service.list_archive_logs(
        user_id=USER_ID,
    )

    assert (
        data[0].cover_image_url
        == (
            "https://signed.example/"
            "users/test/photo.png"
        )
    )

    context.storage_service.create_download_url.assert_called_once_with(
        "users/test/photo.png"
    )


def test_archive_log_pagination() -> None:
    from datetime import timedelta

    records = [
        make_archive_record(
            attendance_log_id="log_003",
            created_at=NOW,
        ),
        make_archive_record(
            attendance_log_id="log_002",
            created_at=NOW - timedelta(minutes=1),
        ),
        make_archive_record(
            attendance_log_id="log_001",
            created_at=NOW - timedelta(minutes=2),
        ),
    ]

    context = make_archive_service(
        records=records,
    )

    first, next_token = (
        context.service.list_archive_logs(
            user_id=USER_ID,
            page_size=2,
        )
    )

    assert [
        item.attendance_log_id
        for item in first
    ] == [
        "log_003",
        "log_002",
    ]

    assert next_token is not None

    second, last_token = (
        context.service.list_archive_logs(
            user_id=USER_ID,
            page_size=2,
            page_token=next_token,
        )
    )

    assert [
        item.attendance_log_id
        for item in second
    ] == [
        "log_001",
    ]

    assert last_token is None


def test_archive_log_rejects_invalid_page_token() -> None:
    context = make_archive_service(
        records=[make_archive_record()],
    )

    with pytest.raises(AppException) as captured:
        context.service.list_archive_logs(
            user_id=USER_ID,
            page_token="not-a-valid-token",
        )

    assert captured.value.status_code == 400
    assert (
        captured.value.code
        == "INVALID_PAGE_TOKEN"
    )


@pytest.mark.parametrize(
    "seat_value",
    [
        "3루 내야 B블록 15열",
        None,
    ],
)
def test_update_log_updates_or_clears_seat(
    seat_value,
) -> None:
    from app.schemas.attendance_log import (
        AttendanceLogUpdateRequest,
    )

    repository = Mock()

    current = make_archive_record()
    repository.get_by_id.return_value = current

    updated = current.model_copy(
        update={"seat": seat_value}
    )
    repository.update.return_value = updated

    service = AttendanceLogService(
        trip_repository=Mock(),
        game_repository=Mock(),
        itinerary_plan_repository=Mock(),
        attendance_log_repository=repository,
        log_entry_repository=Mock(),
    )

    result = service.update_log(
        user_id=USER_ID,
        attendance_log_id="log_001",
        request=AttendanceLogUpdateRequest(
            seat=seat_value
        ),
    )

    assert result.seat == seat_value

    updates = repository.update.call_args.args[1]

    assert "seat" in updates
    assert updates["seat"] == seat_value
    assert "updatedAt" in updates


def test_archive_log_includes_seat() -> None:
    record = make_archive_record().model_copy(
        update={
            "seat": "3루 내야 B블록 15열",
        }
    )

    context = make_archive_service(
        records=[record],
    )

    data, _ = context.service.list_archive_logs(
        user_id=USER_ID,
    )

    assert (
        data[0].seat
        == "3루 내야 B블록 15열"
    )

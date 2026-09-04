from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.attendance_log import (
    AttendanceLogCreateRequest,
    AttendanceLogDocument,
    AttendanceLogRecord,
    AttendanceLogStatus,
    AttendanceLogUpdateRequest,
    LogEntryDocument,
    LogEntryRecord,
    LogEntryType,
    LogEntryUpdateRequest,
    LogMediaCreateRequest,
    LogMediaDocument,
    LogMediaRecord,
    LogMediaType,
)


NOW = datetime(
    2026,
    8,
    13,
    10,
    0,
    tzinfo=timezone.utc,
)


def test_create_request_uses_camel_case() -> None:
    request = AttendanceLogCreateRequest(
        trip_id="trip_001",
        log_title="사직 원정 직관 기록",
    )

    dumped = request.model_dump(
        by_alias=True
    )

    assert dumped["tripId"] == "trip_001"
    assert dumped["logTitle"] == (
        "사직 원정 직관 기록"
    )


def test_create_request_allows_generated_title() -> None:
    request = AttendanceLogCreateRequest(
        trip_id="trip_001"
    )

    assert request.log_title is None


def test_attendance_log_document_matches_erd_fields() -> None:
    document = AttendanceLogDocument(
        user_id="firebase-user-123",
        trip_id="trip_001",
        game_id="game_001",
        plan_id="plan_001",
        log_title="사직 원정 직관 기록",
        summary_text="롯데전 직관과 부산 여행 기록",
        log_status=AttendanceLogStatus.DRAFT,
        created_at=NOW,
        updated_at=NOW,
        deleted_at=None,
    )

    stored = document.model_dump(
        by_alias=True,
        exclude_none=False,
    )

    assert stored["userId"] == (
        "firebase-user-123"
    )
    assert stored["tripId"] == "trip_001"
    assert stored["gameId"] == "game_001"
    assert stored["planId"] == "plan_001"
    assert stored["logTitle"] == (
        "사직 원정 직관 기록"
    )
    assert stored["summaryText"] == (
        "롯데전 직관과 부산 여행 기록"
    )
    assert stored["logStatus"] == "DRAFT"
    assert stored["deletedAt"] is None

    record = AttendanceLogRecord(
        attendance_log_id="log_001",
        **stored,
    )

    assert record.attendance_log_id == (
        "log_001"
    )


def test_attendance_log_update_requires_field() -> None:
    with pytest.raises(ValidationError):
        AttendanceLogUpdateRequest()


def test_log_entry_document_matches_erd_fields() -> None:
    entry = LogEntryDocument(
        plan_item_id="item_1_2",
        place_id="tour_123456",
        sequence_no=2,
        entry_type=LogEntryType.PLACE,
        entry_title="부산 맛집 방문",
        review_text="경기 전에 방문했다.",
        occurred_at=NOW,
        created_at=NOW,
        updated_at=NOW,
    )

    stored = entry.model_dump(
        by_alias=True,
        exclude_none=False,
    )

    assert stored["planItemId"] == "item_1_2"
    assert stored["placeId"] == "tour_123456"
    assert stored["sequenceNo"] == 2
    assert stored["entryType"] == "PLACE"
    assert stored["entryTitle"] == (
        "부산 맛집 방문"
    )
    assert stored["reviewText"] == (
        "경기 전에 방문했다."
    )
    assert stored["occurredAt"] == NOW

    record = LogEntryRecord(
        log_entry_id="entry_001",
        **stored,
    )

    assert record.log_entry_id == "entry_001"


def test_log_entry_update_requires_field() -> None:
    with pytest.raises(ValidationError):
        LogEntryUpdateRequest()


def test_log_media_create_request() -> None:
    request = LogMediaCreateRequest(
        media_type=LogMediaType.IMAGE,
        media_url=(
            "https://example.com/photo.jpg"
        ),
        sequence_no=1,
    )

    stored = request.model_dump(
        by_alias=True
    )

    assert stored["mediaType"] == "IMAGE"
    assert stored["mediaUrl"] == (
        "https://example.com/photo.jpg"
    )
    assert stored["thumbnailUrl"] is None
    assert stored["sequenceNo"] == 1


def test_log_media_document_matches_erd_fields() -> None:
    media = LogMediaDocument(
        media_type=LogMediaType.VIDEO,
        media_url=(
            "https://example.com/video.mp4"
        ),
        thumbnail_url=(
            "https://example.com/thumb.jpg"
        ),
        sequence_no=1,
        created_at=NOW,
    )

    stored = media.model_dump(
        by_alias=True,
        exclude_none=False,
    )

    assert stored["mediaType"] == "VIDEO"
    assert stored["mediaUrl"] == (
        "https://example.com/video.mp4"
    )
    assert stored["thumbnailUrl"] == (
        "https://example.com/thumb.jpg"
    )
    assert stored["sequenceNo"] == 1

    record = LogMediaRecord(
        log_media_id="media_001",
        **stored,
    )

    assert record.log_media_id == "media_001"


def test_attendance_log_defaults_to_private_visibility() -> None:
    from app.schemas.attendance_log import (
        AttendanceLogDocument,
        AttendanceLogStatus,
        AttendanceLogVisibility,
    )

    media_free_log = AttendanceLogDocument(
        user_id="user_001",
        trip_id="trip_001",
        game_id="game_001",
        plan_id="plan_001",
        log_title="직관 기록",
        summary_text=None,
        log_status=AttendanceLogStatus.DRAFT,
        created_at=NOW,
        updated_at=NOW,
        deleted_at=None,
    )

    assert (
        media_free_log.visibility
        == AttendanceLogVisibility.PRIVATE
    )


def test_attendance_log_update_rejects_null_visibility() -> None:
    import pytest
    from pydantic import ValidationError

    from app.schemas.attendance_log import (
        AttendanceLogUpdateRequest,
    )

    with pytest.raises(ValidationError):
        AttendanceLogUpdateRequest(
            visibility=None
        )


def test_attendance_log_support_team_snapshot_uses_camel_case() -> None:
    document = AttendanceLogDocument(
        user_id="firebase-user-123",
        trip_id="trip_001",
        game_id="game_001",
        plan_id="plan_001",
        support_team_id="doosan",
        log_title="직관 기록",
        created_at=NOW,
        updated_at=NOW,
    )

    stored = document.model_dump(
        by_alias=True,
        exclude_none=False,
    )

    assert stored["supportTeamId"] == "doosan"


def test_legacy_attendance_log_allows_missing_support_team_snapshot() -> None:
    document = AttendanceLogDocument(
        user_id="firebase-user-123",
        trip_id="trip_001",
        game_id="game_001",
        plan_id="plan_001",
        log_title="기존 직관 기록",
        created_at=NOW,
        updated_at=NOW,
    )

    assert document.support_team_id is None

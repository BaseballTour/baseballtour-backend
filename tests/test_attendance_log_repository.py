from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from app.repositories.attendance_log_repository import (
    AttendanceLogRepository,
)
from app.schemas.attendance_log import (
    AttendanceLogDocument,
    AttendanceLogStatus,
)


NOW = datetime(
    2026,
    8,
    13,
    10,
    0,
    tzinfo=timezone.utc,
)


def make_document(
    *,
    created_at: datetime = NOW,
):
    return AttendanceLogDocument(
        user_id="user_001",
        trip_id="trip_001",
        game_id="game_001",
        plan_id="plan_001",
        log_title="사직 원정 직관 기록",
        summary_text=None,
        log_status=AttendanceLogStatus.DRAFT,
        created_at=created_at,
        updated_at=created_at,
        deleted_at=None,
    )


def make_stored_data(
    *,
    created_at: datetime = NOW,
    deleted_at=None,
):
    document = make_document(
        created_at=created_at
    )

    data = document.model_dump(
        by_alias=True,
        exclude_none=False,
    )

    data["deletedAt"] = deleted_at

    if deleted_at is not None:
        data["logStatus"] = "ARCHIVED"
        data["updatedAt"] = deleted_at

    return data


def make_snapshot(
    snapshot_id: str,
    data: dict,
    *,
    exists: bool = True,
):
    snapshot = Mock()
    snapshot.id = snapshot_id
    snapshot.exists = exists
    snapshot.to_dict.return_value = data
    return snapshot


def test_create_stores_firestore_aliases() -> None:
    client = Mock()
    collection = client.collection.return_value

    reference = collection.document.return_value
    reference.id = "log_001"

    repository = AttendanceLogRepository(
        client=client
    )

    result = repository.create(
        make_document()
    )

    generated_id = collection.document.call_args.args[0]
    assert generated_id.startswith("log_")
    assert result.attendance_log_id == "log_001"
    assert result.trip_id == "trip_001"

    stored = reference.set.call_args.args[0]

    assert stored["userId"] == "user_001"
    assert stored["tripId"] == "trip_001"
    assert stored["gameId"] == "game_001"
    assert stored["planId"] == "plan_001"
    assert stored["logTitle"] == (
        "사직 원정 직관 기록"
    )
    assert stored["logStatus"] == "DRAFT"
    assert stored["deletedAt"] is None


def test_get_by_id_returns_active_log() -> None:
    client = Mock()
    collection = client.collection.return_value

    snapshot = make_snapshot(
        "log_001",
        make_stored_data(),
    )

    collection.document.return_value.get.return_value = (
        snapshot
    )

    repository = AttendanceLogRepository(
        client=client
    )

    result = repository.get_by_id(
        "log_001"
    )

    assert result is not None
    assert result.attendance_log_id == "log_001"
    assert result.user_id == "user_001"


def test_get_by_id_hides_deleted_log() -> None:
    client = Mock()
    collection = client.collection.return_value

    snapshot = make_snapshot(
        "log_001",
        make_stored_data(
            deleted_at=NOW,
        ),
    )

    collection.document.return_value.get.return_value = (
        snapshot
    )

    repository = AttendanceLogRepository(
        client=client
    )

    assert (
        repository.get_by_id("log_001")
        is None
    )

    deleted = repository.get_by_id(
        "log_001",
        include_deleted=True,
    )

    assert deleted is not None
    assert deleted.deleted_at == NOW


def test_get_by_user_id_excludes_deleted_and_sorts() -> None:
    client = Mock()
    collection = client.collection.return_value
    query = collection.where.return_value

    older = make_snapshot(
        "log_old",
        make_stored_data(
            created_at=NOW,
        ),
    )

    newer = make_snapshot(
        "log_new",
        make_stored_data(
            created_at=NOW + timedelta(hours=1),
        ),
    )

    deleted = make_snapshot(
        "log_deleted",
        make_stored_data(
            created_at=NOW + timedelta(hours=2),
            deleted_at=NOW + timedelta(hours=3),
        ),
    )

    query.stream.return_value = [
        older,
        deleted,
        newer,
    ]

    repository = AttendanceLogRepository(
        client=client
    )

    result = repository.get_by_user_id(
        "user_001"
    )

    assert [
        log.attendance_log_id
        for log in result
    ] == [
        "log_new",
        "log_old",
    ]


def test_get_active_by_trip_id_returns_latest_active() -> None:
    client = Mock()
    collection = client.collection.return_value
    query = collection.where.return_value

    older = make_snapshot(
        "log_old",
        make_stored_data(
            created_at=NOW,
        ),
    )

    newer = make_snapshot(
        "log_new",
        make_stored_data(
            created_at=NOW + timedelta(hours=1),
        ),
    )

    deleted = make_snapshot(
        "log_deleted",
        make_stored_data(
            created_at=NOW + timedelta(hours=2),
            deleted_at=NOW + timedelta(hours=3),
        ),
    )

    query.stream.return_value = [
        older,
        newer,
        deleted,
    ]

    repository = AttendanceLogRepository(
        client=client
    )

    result = repository.get_active_by_trip_id(
        "trip_001"
    )

    assert result is not None
    assert result.attendance_log_id == "log_new"


def test_soft_delete_archives_log() -> None:
    client = Mock()
    collection = client.collection.return_value
    reference = collection.document.return_value

    reference.get.return_value = make_snapshot(
        "log_001",
        make_stored_data(),
    )

    repository = AttendanceLogRepository(
        client=client
    )

    deleted_at = NOW + timedelta(hours=1)

    result = repository.soft_delete(
        "log_001",
        deleted_at=deleted_at,
    )

    assert result is True

    reference.update.assert_called_once_with(
        {
            "logStatus": "ARCHIVED",
            "updatedAt": deleted_at,
            "deletedAt": deleted_at,
        }
    )

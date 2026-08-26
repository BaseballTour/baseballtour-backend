from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from app.repositories.log_entry_repository import (
    LogEntryRepository,
)
from app.schemas.attendance_log import (
    LogEntryDocument,
    LogEntryType,
)


NOW = datetime(
    2026,
    8,
    19,
    3,
    0,
    tzinfo=timezone.utc,
)


def make_document(
    *,
    sequence_no: int = 1,
    entry_title: str = "광안리해수욕장",
    updated_at: datetime = NOW,
) -> LogEntryDocument:
    return LogEntryDocument(
        plan_item_id="item_001",
        place_id="tour_001",
        sequence_no=sequence_no,
        entry_type=LogEntryType.PLACE,
        entry_title=entry_title,
        review_text=None,
        occurred_at=None,
        created_at=NOW,
        updated_at=updated_at,
    )


def make_stored_data(
    *,
    sequence_no: int = 1,
    entry_title: str = "광안리해수욕장",
    updated_at: datetime = NOW,
) -> dict:
    return make_document(
        sequence_no=sequence_no,
        entry_title=entry_title,
        updated_at=updated_at,
    ).model_dump(
        by_alias=True,
        exclude_none=False,
    )


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


def make_repository():
    client = Mock()

    attendance_collection = (
        client.collection.return_value
    )

    attendance_log_reference = (
        attendance_collection
        .document.return_value
    )

    entries_collection = (
        attendance_log_reference
        .collection.return_value
    )

    repository = LogEntryRepository(
        client=client
    )

    return (
        repository,
        attendance_log_reference,
        entries_collection,
    )


def test_create_stores_firestore_aliases() -> None:
    (
        repository,
        attendance_log_reference,
        entries_collection,
    ) = make_repository()

    reference = (
        entries_collection.document.return_value
    )
    reference.id = "entry_001"

    result = repository.create(
        "log_001",
        make_document(),
    )

    generated_id = entries_collection.document.call_args.args[0]
    assert generated_id.startswith("entry_")
    assert result.log_entry_id == "entry_001"
    assert result.sequence_no == 1
    assert result.entry_type == LogEntryType.PLACE

    attendance_log_reference.collection.assert_called_once_with(
        "entries"
    )

    stored = reference.set.call_args.args[0]

    assert stored["planItemId"] == "item_001"
    assert stored["placeId"] == "tour_001"
    assert stored["sequenceNo"] == 1
    assert stored["entryType"] == "PLACE"
    assert stored["entryTitle"] == "광안리해수욕장"
    assert stored["reviewText"] is None
    assert stored["occurredAt"] is None
    assert stored["createdAt"] == NOW
    assert stored["updatedAt"] == NOW


def test_get_by_id_returns_entry() -> None:
    (
        repository,
        _,
        entries_collection,
    ) = make_repository()

    snapshot = make_snapshot(
        "entry_001",
        make_stored_data(),
    )

    (
        entries_collection
        .document.return_value
        .get.return_value
    ) = snapshot

    result = repository.get_by_id(
        "log_001",
        "entry_001",
    )

    assert result is not None
    assert result.log_entry_id == "entry_001"
    assert result.place_id == "tour_001"
    assert result.sequence_no == 1


def test_get_by_id_returns_none_when_missing() -> None:
    (
        repository,
        _,
        entries_collection,
    ) = make_repository()

    snapshot = make_snapshot(
        "entry_missing",
        {},
        exists=False,
    )

    (
        entries_collection
        .document.return_value
        .get.return_value
    ) = snapshot

    result = repository.get_by_id(
        "log_001",
        "entry_missing",
    )

    assert result is None


def test_get_all_sorts_by_sequence_no() -> None:
    (
        repository,
        _,
        entries_collection,
    ) = make_repository()

    entries_collection.stream.return_value = [
        make_snapshot(
            "entry_003",
            make_stored_data(
                sequence_no=3,
            ),
        ),
        make_snapshot(
            "entry_001",
            make_stored_data(
                sequence_no=1,
            ),
        ),
        make_snapshot(
            "entry_002",
            make_stored_data(
                sequence_no=2,
            ),
        ),
    ]

    result = repository.get_all(
        "log_001"
    )

    assert [
        entry.log_entry_id
        for entry in result
    ] == [
        "entry_001",
        "entry_002",
        "entry_003",
    ]

    assert [
        entry.sequence_no
        for entry in result
    ] == [
        1,
        2,
        3,
    ]


def test_update_returns_updated_entry() -> None:
    (
        repository,
        _,
        entries_collection,
    ) = make_repository()

    reference = (
        entries_collection.document.return_value
    )

    updated_at = NOW + timedelta(
        hours=1
    )

    before = make_snapshot(
        "entry_001",
        make_stored_data(),
    )

    after = make_snapshot(
        "entry_001",
        make_stored_data(
            entry_title="광안리 방문",
            updated_at=updated_at,
        ),
    )

    reference.get.side_effect = [
        before,
        after,
    ]

    result = repository.update(
        "log_001",
        "entry_001",
        {
            "entryTitle": "광안리 방문",
            "updatedAt": updated_at,
        },
    )

    assert result is not None
    assert result.entry_title == "광안리 방문"
    assert result.updated_at == updated_at

    reference.update.assert_called_once_with(
        {
            "entryTitle": "광안리 방문",
            "updatedAt": updated_at,
        }
    )


def test_update_returns_none_when_missing() -> None:
    (
        repository,
        _,
        entries_collection,
    ) = make_repository()

    reference = (
        entries_collection.document.return_value
    )

    reference.get.return_value = (
        make_snapshot(
            "entry_missing",
            {},
            exists=False,
        )
    )

    result = repository.update(
        "log_001",
        "entry_missing",
        {
            "entryTitle": "수정",
        },
    )

    assert result is None
    reference.update.assert_not_called()


def test_delete_removes_existing_entry() -> None:
    (
        repository,
        _,
        entries_collection,
    ) = make_repository()

    reference = (
        entries_collection.document.return_value
    )

    reference.get.return_value = (
        make_snapshot(
            "entry_001",
            make_stored_data(),
        )
    )

    result = repository.delete(
        "log_001",
        "entry_001",
    )

    assert result is True
    reference.delete.assert_called_once_with()


def test_delete_returns_false_when_missing() -> None:
    (
        repository,
        _,
        entries_collection,
    ) = make_repository()

    reference = (
        entries_collection.document.return_value
    )

    reference.get.return_value = (
        make_snapshot(
            "entry_missing",
            {},
            exists=False,
        )
    )

    result = repository.delete(
        "log_001",
        "entry_missing",
    )

    assert result is False
    reference.delete.assert_not_called()

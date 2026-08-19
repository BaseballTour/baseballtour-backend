from datetime import datetime, timezone
from unittest.mock import Mock

from app.repositories.log_media_repository import (
    LogMediaRepository,
)
from app.schemas.attendance_log import (
    LogMediaDocument,
    LogMediaType,
)


NOW = datetime(
    2026,
    8,
    19,
    5,
    30,
    tzinfo=timezone.utc,
)


def make_document(
    *,
    media_type: LogMediaType = LogMediaType.IMAGE,
    media_url: str = "https://example.com/photo.jpg",
    thumbnail_url: str | None = None,
    sequence_no: int = 1,
) -> LogMediaDocument:
    return LogMediaDocument(
        media_type=media_type,
        media_url=media_url,
        thumbnail_url=thumbnail_url,
        sequence_no=sequence_no,
        created_at=NOW,
    )


def make_stored_data(
    *,
    media_type: LogMediaType = LogMediaType.IMAGE,
    media_url: str = "https://example.com/photo.jpg",
    thumbnail_url: str | None = None,
    sequence_no: int = 1,
) -> dict:
    return make_document(
        media_type=media_type,
        media_url=media_url,
        thumbnail_url=thumbnail_url,
        sequence_no=sequence_no,
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

    entry_reference = (
        entries_collection
        .document.return_value
    )

    media_collection = (
        entry_reference
        .collection.return_value
    )

    repository = LogMediaRepository(
        client=client
    )

    return (
        repository,
        attendance_log_reference,
        entries_collection,
        entry_reference,
        media_collection,
    )


def test_create_stores_firestore_aliases() -> None:
    (
        repository,
        attendance_log_reference,
        entries_collection,
        entry_reference,
        media_collection,
    ) = make_repository()

    reference = (
        media_collection.document.return_value
    )
    reference.id = "media_001"

    result = repository.create(
        "log_001",
        "entry_001",
        make_document(),
    )

    assert result.log_media_id == "media_001"
    assert result.media_type == LogMediaType.IMAGE
    assert result.sequence_no == 1

    attendance_log_reference.collection.assert_called_once_with(
        "entries"
    )

    entries_collection.document.assert_called_once_with(
        "entry_001"
    )

    entry_reference.collection.assert_called_once_with(
        "media"
    )

    stored = reference.set.call_args.args[0]

    assert stored["mediaType"] == "IMAGE"
    assert stored["mediaUrl"] == (
        "https://example.com/photo.jpg"
    )
    assert stored["thumbnailUrl"] is None
    assert stored["sequenceNo"] == 1
    assert stored["createdAt"] == NOW


def test_get_all_sorts_by_sequence_no() -> None:
    (
        repository,
        _,
        _,
        _,
        media_collection,
    ) = make_repository()

    media_collection.stream.return_value = [
        make_snapshot(
            "media_003",
            make_stored_data(
                sequence_no=3,
            ),
        ),
        make_snapshot(
            "media_001",
            make_stored_data(
                sequence_no=1,
            ),
        ),
        make_snapshot(
            "media_002",
            make_stored_data(
                media_type=LogMediaType.VIDEO,
                media_url=(
                    "https://example.com/video.mp4"
                ),
                thumbnail_url=(
                    "https://example.com/thumb.jpg"
                ),
                sequence_no=2,
            ),
        ),
    ]

    result = repository.get_all(
        "log_001",
        "entry_001",
    )

    assert [
        media.log_media_id
        for media in result
    ] == [
        "media_001",
        "media_002",
        "media_003",
    ]

    assert [
        media.sequence_no
        for media in result
    ] == [
        1,
        2,
        3,
    ]


def test_delete_removes_existing_media() -> None:
    (
        repository,
        _,
        _,
        _,
        media_collection,
    ) = make_repository()

    reference = (
        media_collection.document.return_value
    )

    reference.get.return_value = (
        make_snapshot(
            "media_001",
            make_stored_data(),
        )
    )

    result = repository.delete(
        "log_001",
        "entry_001",
        "media_001",
    )

    assert result is True

    media_collection.document.assert_called_once_with(
        "media_001"
    )

    reference.delete.assert_called_once_with()


def test_delete_returns_false_when_missing() -> None:
    (
        repository,
        _,
        _,
        _,
        media_collection,
    ) = make_repository()

    reference = (
        media_collection.document.return_value
    )

    reference.get.return_value = (
        make_snapshot(
            "media_missing",
            {},
            exists=False,
        )
    )

    result = repository.delete(
        "log_001",
        "entry_001",
        "media_missing",
    )

    assert result is False
    reference.delete.assert_not_called()

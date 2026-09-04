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
    9,
    1,
    1,
    0,
    tzinfo=timezone.utc,
)


def make_media(
    *,
    path: str = (
        "users/user_001/attendance-logs/"
        "log_001/entry_001/media_001.jpg"
    ),
    sequence_no: int = 1,
) -> LogMediaDocument:
    return LogMediaDocument(
        media_type=LogMediaType.IMAGE,
        storage_path=path,
        content_type="image/jpeg",
        media_url=None,
        thumbnail_url=None,
        sequence_no=sequence_no,
        created_at=NOW,
    )


def make_repository():
    client = Mock()

    attendance = client.collection.return_value
    log_ref = attendance.document.return_value
    entries = log_ref.collection.return_value
    entry_ref = entries.document.return_value
    media_collection = (
        entry_ref.collection.return_value
    )

    repository = LogMediaRepository(
        client=client
    )

    return repository, media_collection


def make_snapshot(
    snapshot_id: str,
    media: LogMediaDocument,
):
    snapshot = Mock()
    snapshot.id = snapshot_id
    snapshot.exists = True
    snapshot.to_dict.return_value = (
        media.model_dump(
            by_alias=True,
            exclude_none=False,
        )
    )
    return snapshot


def test_create_media_stores_storage_path() -> None:
    repository, media_collection = (
        make_repository()
    )

    reference = (
        media_collection.document.return_value
    )
    reference.id = "media_001"

    result = repository.create(
        "log_001",
        "entry_001",
        make_media(),
    )

    assert result.log_media_id == "media_001"
    assert result.content_type == "image/jpeg"

    stored = reference.set.call_args.args[0]

    assert stored["storagePath"].endswith(
        "media_001.jpg"
    )
    assert stored["contentType"] == "image/jpeg"
    assert stored["mediaType"] == "IMAGE"
    assert stored["mediaUrl"] is None


def test_get_all_sorts_media() -> None:
    repository, media_collection = (
        make_repository()
    )

    media_collection.stream.return_value = [
        make_snapshot(
            "media_002",
            make_media(
                path="users/u/x/media_002.jpg",
                sequence_no=2,
            ),
        ),
        make_snapshot(
            "media_001",
            make_media(
                path="users/u/x/media_001.jpg",
                sequence_no=1,
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
    ]


def test_get_by_storage_path() -> None:
    repository, media_collection = (
        make_repository()
    )

    target = (
        "users/user_001/attendance-logs/"
        "log_001/entry_001/media_001.jpg"
    )

    media_collection.stream.return_value = [
        make_snapshot(
            "media_001",
            make_media(
                path=target,
            ),
        )
    ]

    result = repository.get_by_storage_path(
        "log_001",
        "entry_001",
        target,
    )

    assert result is not None
    assert result.log_media_id == "media_001"


def test_get_by_id_returns_media() -> None:
    repository, media_collection = (
        make_repository()
    )

    media = make_media()

    snapshot = make_snapshot(
        "media_001",
        media,
    )

    media_collection.document.return_value.get.return_value = (
        snapshot
    )

    result = repository.get_by_id(
        "log_001",
        "entry_001",
        "media_001",
    )

    assert result is not None
    assert result.log_media_id == "media_001"
    assert result.storage_path == (
        media.storage_path
    )


def test_get_by_id_returns_none_when_missing() -> None:
    repository, media_collection = (
        make_repository()
    )

    snapshot = Mock()
    snapshot.exists = False

    media_collection.document.return_value.get.return_value = (
        snapshot
    )

    result = repository.get_by_id(
        "log_001",
        "entry_001",
        "media_missing",
    )

    assert result is None

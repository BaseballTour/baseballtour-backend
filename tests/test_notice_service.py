from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from app.core.exceptions import AppException
from app.repositories.notice_repository import NoticeRepository
from app.schemas.notice import NoticeRecord
from app.services.notice_service import NoticeService


def make_notice(
    notice_id: str = "notice_001",
    *,
    published: bool = True,
    day: int = 15,
) -> NoticeRecord:
    now = datetime(2026, 8, day, 10, 0, tzinfo=timezone.utc)
    return NoticeRecord(
        notice_id=notice_id,
        title="서비스 점검 안내",
        content="서비스 점검이 진행됩니다.",
        is_published=published,
        published_at=now if published else None,
        created_at=now,
        updated_at=now,
    )


def test_notice_service_returns_summary_list() -> None:
    repository = Mock()
    repository.get_published.return_value = [make_notice()]
    service = NoticeService(repository=repository)

    notices = service.get_notices()

    assert len(notices) == 1
    assert notices[0].notice_id == "notice_001"
    assert notices[0].title == "서비스 점검 안내"
    assert not hasattr(notices[0], "content")


def test_notice_service_returns_detail() -> None:
    repository = Mock()
    repository.get_published_by_id.return_value = make_notice()
    service = NoticeService(repository=repository)

    notice = service.get_notice("notice_001")

    assert notice.notice_id == "notice_001"
    assert notice.content == "서비스 점검이 진행됩니다."
    repository.get_published_by_id.assert_called_once_with("notice_001")


def test_notice_service_returns_404_for_missing_notice() -> None:
    repository = Mock()
    repository.get_published_by_id.return_value = None
    service = NoticeService(repository=repository)

    with pytest.raises(AppException) as exc_info:
        service.get_notice("missing")

    assert exc_info.value.status_code == 404
    assert exc_info.value.code == "NOTICE_NOT_FOUND"


def test_notice_document_rejects_published_without_date() -> None:
    from pydantic import ValidationError
    from app.schemas.notice import NoticeDocument

    now = datetime(2026, 8, 15, tzinfo=timezone.utc)

    with pytest.raises(ValidationError):
        NoticeDocument(
            title="공지",
            content="본문",
            is_published=True,
            published_at=None,
            created_at=now,
            updated_at=now,
        )


def test_notice_repository_filters_and_sorts_published() -> None:
    client = Mock()
    collection = client.collection.return_value
    query = collection.where.return_value

    def snapshot(notice: NoticeRecord) -> Mock:
        document = Mock()
        document.id = notice.notice_id
        document.to_dict.return_value = notice.model_dump(
            by_alias=True,
            exclude={"notice_id"},
        )
        return document

    query.stream.return_value = [
        snapshot(make_notice("old", day=14)),
        snapshot(make_notice("new", day=16)),
        snapshot(make_notice("middle", day=15)),
    ]

    repository = NoticeRepository(client=client)
    notices = repository.get_published()

    assert [notice.notice_id for notice in notices] == [
        "new",
        "middle",
        "old",
    ]
    assert collection.where.call_count == 1
    assert query.stream.call_count == 1


def test_notice_repository_hides_unpublished_detail() -> None:
    client = Mock()
    document = client.collection.return_value.document.return_value.get.return_value
    document.exists = True
    document.to_dict.return_value = make_notice(
        published=False,
    ).model_dump(
        by_alias=True,
        exclude={"notice_id"},
    )

    repository = NoticeRepository(client=client)

    assert repository.get_published_by_id("notice_001") is None


def test_notice_repository_returns_none_for_missing_document() -> None:
    client = Mock()
    document = client.collection.return_value.document.return_value.get.return_value
    document.exists = False

    repository = NoticeRepository(client=client)

    assert repository.get_published_by_id("missing") is None

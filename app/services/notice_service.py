from fastapi import status

from app.core.exceptions import AppException
from app.repositories.notice_repository import NoticeRepository
from app.schemas.notice import (
    NoticeDetailResponse,
    NoticeRecord,
    NoticeSummaryResponse,
)


class NoticeService:
    """공개 공지사항 조회 비즈니스 로직을 담당합니다."""

    def __init__(
        self,
        repository: NoticeRepository | None = None,
    ) -> None:
        self._repository = repository or NoticeRepository()

    def get_notices(self) -> list[NoticeSummaryResponse]:
        notices = self._repository.get_published()

        return [
            self._to_summary(notice)
            for notice in notices
        ]

    def get_notice(
        self,
        notice_id: str,
    ) -> NoticeDetailResponse:
        notice = self._repository.get_published_by_id(
            notice_id
        )

        if notice is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="NOTICE_NOT_FOUND",
                message="공지사항을 찾을 수 없습니다.",
            )

        return NoticeDetailResponse(
            notice_id=notice.notice_id,
            title=notice.title,
            published_at=notice.published_at,
            content=notice.content,
        )

    @staticmethod
    def _to_summary(
        notice: NoticeRecord,
    ) -> NoticeSummaryResponse:
        return NoticeSummaryResponse(
            notice_id=notice.notice_id,
            title=notice.title,
            published_at=notice.published_at,
        )

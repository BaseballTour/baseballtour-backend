from datetime import datetime

from pydantic import Field, model_validator

from app.schemas.base import ApiModel


class NoticeDocument(ApiModel):
    """Firestore notices 문서."""

    title: str = Field(min_length=1)
    content: str = Field(min_length=1)
    is_published: bool = False
    published_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_publication(self) -> "NoticeDocument":
        if self.is_published and self.published_at is None:
            raise ValueError(
                "공개된 공지에는 publishedAt이 필요합니다."
            )
        return self


class NoticeRecord(NoticeDocument):
    notice_id: str


class NoticeSummaryResponse(ApiModel):
    notice_id: str
    title: str
    published_at: datetime


class NoticeDetailResponse(NoticeSummaryResponse):
    content: str

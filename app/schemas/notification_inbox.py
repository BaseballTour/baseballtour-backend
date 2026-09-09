from pydantic import AwareDatetime, Field, computed_field

from app.schemas.base import ApiModel


class NotificationDocument(ApiModel):
    """사용자별 알림 Firestore 문서."""

    type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    created_at: AwareDatetime
    read_at: AwareDatetime | None = None
    target_type: str | None = None
    target_id: str | None = None


class NotificationRecord(NotificationDocument):
    notification_id: str


class NotificationResponse(NotificationRecord):
    @computed_field(alias="isRead")
    @property
    def is_read(self) -> bool:
        return self.read_at is not None


class NotificationUnreadCountResponse(ApiModel):
    unread_count: int = Field(ge=0)

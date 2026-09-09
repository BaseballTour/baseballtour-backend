from app.repositories.notification_inbox_repository import (
    NotificationInboxRepository,
)
from app.schemas.notification_inbox import (
    NotificationRecord,
)


class NotificationInboxService:
    def __init__(
        self,
        repository: NotificationInboxRepository | None = None,
    ) -> None:
        self._repository = repository or NotificationInboxRepository()

    def get_notifications(
        self,
        *,
        user_id: str,
        page_size: int,
        page_token: str | None = None,
    ) -> tuple[list[NotificationRecord], str | None]:
        return self._repository.get_page(
            user_id=user_id,
            page_size=page_size,
            page_token=page_token,
        )

    def get_unread_count(self, *, user_id: str) -> int:
        return self._repository.get_unread_count(user_id=user_id)

    def mark_read(
        self,
        *,
        user_id: str,
        notification_id: str,
    ) -> NotificationRecord | None:
        return self._repository.mark_read(
            user_id=user_id,
            notification_id=notification_id,
        )

from datetime import datetime, timezone
from uuid import uuid4

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.client import Client

from app.core.firebase import get_firestore_client
from app.schemas.notification_inbox import (
    NotificationDocument,
    NotificationRecord,
)


class InvalidNotificationPageToken(ValueError):
    pass


class NotificationInboxRepository:
    USERS_COLLECTION = "users"
    COLLECTION = "notifications"

    def __init__(self, client: Client | None = None) -> None:
        self._client = client or get_firestore_client()

    def _collection(self, user_id: str):
        return (
            self._client.collection(self.USERS_COLLECTION)
            .document(user_id)
            .collection(self.COLLECTION)
        )

    @staticmethod
    def _record(snapshot) -> NotificationRecord:
        return NotificationRecord(
            notification_id=snapshot.id,
            **(snapshot.to_dict() or {}),
        )

    def get_page(
        self,
        *,
        user_id: str,
        page_size: int,
        page_token: str | None = None,
    ) -> tuple[list[NotificationRecord], str | None]:
        collection = self._collection(user_id)

        query = (
            collection
            .order_by(
                "createdAt",
                direction=firestore.Query.DESCENDING,
            )
            .order_by(
                "__name__",
                direction=firestore.Query.DESCENDING,
            )
        )

        if page_token is not None:
            if not page_token or "/" in page_token or len(page_token) > 256:
                raise InvalidNotificationPageToken()

            cursor = collection.document(page_token).get()
            if not cursor.exists:
                raise InvalidNotificationPageToken()

            query = query.start_after(cursor)

        snapshots = list(query.limit(page_size + 1).stream())
        has_more = len(snapshots) > page_size
        page = snapshots[:page_size]

        records = [self._record(snapshot) for snapshot in page]
        next_token = page[-1].id if has_more else None

        return records, next_token

    def get_unread_count(self, *, user_id: str) -> int:
        query = self._collection(user_id).where(
            filter=FieldFilter("readAt", "==", None)
        )
        result = query.count(alias="unreadCount").get()
        return int(result[0][0].value)

    def mark_read(
        self,
        *,
        user_id: str,
        notification_id: str,
    ) -> NotificationRecord | None:
        if not notification_id or "/" in notification_id:
            return None

        reference = self._collection(user_id).document(notification_id)
        transaction = self._client.transaction()

        @firestore.transactional
        def update_read_at(transaction):
            snapshot = reference.get(transaction=transaction)
            if not snapshot.exists:
                return None

            record = self._record(snapshot)
            if record.read_at is not None:
                return record

            read_at = datetime.now(timezone.utc)
            transaction.update(reference, {"readAt": read_at})
            return record.model_copy(update={"read_at": read_at})

        return update_read_at(transaction)

    def create_notification(
        self,
        *,
        user_id: str,
        notification: NotificationDocument,
    ) -> NotificationRecord:
        """서버 내부의 알림 생성 로직에서 사용합니다."""
        notification_id = f"notification_{uuid4().hex}"
        self._collection(user_id).document(notification_id).create(
            notification.model_dump(
                by_alias=True,
                mode="python",
                exclude_none=False,
            )
        )
        return NotificationRecord(
            notification_id=notification_id,
            **notification.model_dump(),
        )

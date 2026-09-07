from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.client import Client

from app.core.firebase import get_firestore_client
from app.schemas.notice import NoticeRecord


class NoticeRepository:
    """Firestore notices Collection 접근을 담당합니다."""

    COLLECTION_NAME = "notices"

    def __init__(self, client: Client | None = None) -> None:
        self._client = client or get_firestore_client()
        self._collection = self._client.collection(
            self.COLLECTION_NAME
        )

    def get_published(self) -> list[NoticeRecord]:
        """공개된 공지 목록을 최신 게시일순으로 조회합니다."""
        query = self._collection.where(
            filter=FieldFilter("isPublished", "==", True)
        )

        notices: list[NoticeRecord] = []

        for document in query.stream():
            data = document.to_dict() or {}
            notices.append(
                NoticeRecord(
                    notice_id=document.id,
                    **data,
                )
            )

        return sorted(
            notices,
            key=lambda notice: (
                notice.published_at,
                notice.notice_id,
            ),
            reverse=True,
        )

    def get_published_by_id(
        self,
        notice_id: str,
    ) -> NoticeRecord | None:
        """공개된 공지만 ID로 조회합니다."""
        document = self._collection.document(
            notice_id
        ).get()

        if not document.exists:
            return None

        data = document.to_dict() or {}

        if data.get("isPublished") is not True:
            return None

        return NoticeRecord(
            notice_id=document.id,
            **data,
        )

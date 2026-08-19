from google.cloud.firestore_v1.client import Client

from app.core.firebase import get_firestore_client
from app.schemas.attendance_log import (
    LogMediaDocument,
    LogMediaRecord,
)


class LogMediaRepository:
    """Firestore 로그 Entry의 media 하위 Collection 접근을 담당합니다."""

    COLLECTION_NAME = "attendanceLogs"
    ENTRY_SUBCOLLECTION_NAME = "entries"
    MEDIA_SUBCOLLECTION_NAME = "media"

    def __init__(
        self,
        client: Client | None = None,
    ) -> None:
        self._client = client or get_firestore_client()
        self._attendance_log_collection = (
            self._client.collection(
                self.COLLECTION_NAME
            )
        )

    def _media_collection(
        self,
        attendance_log_id: str,
        log_entry_id: str,
    ):
        """로그 Entry의 media 하위 Collection을 반환합니다."""

        return (
            self._attendance_log_collection
            .document(attendance_log_id)
            .collection(
                self.ENTRY_SUBCOLLECTION_NAME
            )
            .document(log_entry_id)
            .collection(
                self.MEDIA_SUBCOLLECTION_NAME
            )
        )

    def create(
        self,
        attendance_log_id: str,
        log_entry_id: str,
        media: LogMediaDocument,
    ) -> LogMediaRecord:
        """Firestore Auto ID로 로그 미디어를 생성합니다."""

        collection = self._media_collection(
            attendance_log_id,
            log_entry_id,
        )

        document_reference = (
            collection.document()
        )

        document_reference.set(
            media.model_dump(
                by_alias=True,
                exclude_none=False,
            )
        )

        return LogMediaRecord(
            log_media_id=document_reference.id,
            **media.model_dump(),
        )

    def get_all(
        self,
        attendance_log_id: str,
        log_entry_id: str,
    ) -> list[LogMediaRecord]:
        """Entry의 모든 미디어를 sequenceNo 순으로 조회합니다."""

        collection = self._media_collection(
            attendance_log_id,
            log_entry_id,
        )

        media_items: list[LogMediaRecord] = []

        for snapshot in collection.stream():
            data = snapshot.to_dict() or {}

            media_items.append(
                LogMediaRecord(
                    log_media_id=snapshot.id,
                    **data,
                )
            )

        return sorted(
            media_items,
            key=lambda media: media.sequence_no,
        )

    def delete(
        self,
        attendance_log_id: str,
        log_entry_id: str,
        log_media_id: str,
    ) -> bool:
        """
        로그 미디어를 실제 삭제합니다.

        ERD의 log_media에는 deletedAt이 없으므로
        Soft Delete를 사용하지 않습니다.
        """

        collection = self._media_collection(
            attendance_log_id,
            log_entry_id,
        )

        document_reference = (
            collection.document(
                log_media_id
            )
        )

        snapshot = document_reference.get()

        if not snapshot.exists:
            return False

        document_reference.delete()

        return True

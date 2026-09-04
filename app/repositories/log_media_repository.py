from google.cloud.firestore_v1.client import Client

from app.core.firebase import get_firestore_client
from app.core.ids import new_prefixed_id
from app.schemas.attendance_log import (
    LogMediaDocument,
    LogMediaRecord,
)


class LogMediaRepository:
    """로그 Entry의 media 하위 Collection 접근."""

    COLLECTION_NAME = "attendanceLogs"
    ENTRY_SUBCOLLECTION_NAME = "entries"
    MEDIA_SUBCOLLECTION_NAME = "media"

    def __init__(
        self,
        client: Client | None = None,
    ) -> None:
        self._client = client or get_firestore_client()

        self._attendance_logs = (
            self._client.collection(
                self.COLLECTION_NAME
            )
        )

    def _media_collection(
        self,
        attendance_log_id: str,
        log_entry_id: str,
    ):
        return (
            self._attendance_logs
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
        collection = self._media_collection(
            attendance_log_id,
            log_entry_id,
        )

        reference = collection.document(
            new_prefixed_id("media")
        )

        reference.set(
            media.model_dump(
                by_alias=True,
                exclude_none=False,
            )
        )

        return LogMediaRecord(
            log_media_id=reference.id,
            **media.model_dump(),
        )

    def get_all(
        self,
        attendance_log_id: str,
        log_entry_id: str,
    ) -> list[LogMediaRecord]:
        collection = self._media_collection(
            attendance_log_id,
            log_entry_id,
        )

        media: list[LogMediaRecord] = []

        for snapshot in collection.stream():
            data = snapshot.to_dict() or {}

            media.append(
                LogMediaRecord(
                    log_media_id=snapshot.id,
                    **data,
                )
            )

        return sorted(
            media,
            key=lambda item: item.sequence_no,
        )

    def get_by_id(
        self,
        attendance_log_id: str,
        log_entry_id: str,
        log_media_id: str,
    ) -> LogMediaRecord | None:
        """로그 미디어 ID로 단건 조회합니다."""

        collection = self._media_collection(
            attendance_log_id,
            log_entry_id,
        )

        snapshot = collection.document(
            log_media_id
        ).get()

        if not snapshot.exists:
            return None

        data = snapshot.to_dict() or {}

        return LogMediaRecord(
            log_media_id=snapshot.id,
            **data,
        )

    def get_by_storage_path(
        self,
        attendance_log_id: str,
        log_entry_id: str,
        storage_path: str,
    ) -> LogMediaRecord | None:
        for media in self.get_all(
            attendance_log_id,
            log_entry_id,
        ):
            if media.storage_path == storage_path:
                return media

        return None

    def delete(
        self,
        attendance_log_id: str,
        log_entry_id: str,
        log_media_id: str,
    ) -> bool:
        collection = self._media_collection(
            attendance_log_id,
            log_entry_id,
        )

        reference = collection.document(
            log_media_id
        )

        snapshot = reference.get()

        if not snapshot.exists:
            return False

        reference.delete()

        return True

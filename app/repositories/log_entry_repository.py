from typing import Any

from google.cloud.firestore_v1.client import Client

from app.core.firebase import get_firestore_client
from app.core.ids import new_prefixed_id
from app.schemas.attendance_log import (
    LogEntryDocument,
    LogEntryRecord,
)


class LogEntryRepository:
    """Firestore attendanceLogs/{logId}/entries 접근을 담당합니다."""

    COLLECTION_NAME = "attendanceLogs"
    SUBCOLLECTION_NAME = "entries"

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

    def _entries_collection(
        self,
        attendance_log_id: str,
    ):
        """직관 로그의 entries 하위 Collection을 반환합니다."""

        return (
            self._attendance_log_collection
            .document(attendance_log_id)
            .collection(self.SUBCOLLECTION_NAME)
        )

    def create(
        self,
        attendance_log_id: str,
        entry: LogEntryDocument,
    ) -> LogEntryRecord:
        """`entry_` 접두사 ID로 로그 Entry를 생성합니다."""

        collection = self._entries_collection(
            attendance_log_id
        )

        document_reference = collection.document(
            new_prefixed_id("entry")
        )

        document_reference.set(
            entry.model_dump(
                by_alias=True,
                exclude_none=False,
            )
        )

        return LogEntryRecord(
            log_entry_id=document_reference.id,
            **entry.model_dump(),
        )

    def get_by_id(
        self,
        attendance_log_id: str,
        log_entry_id: str,
    ) -> LogEntryRecord | None:
        """로그 Entry ID로 문서를 조회합니다."""

        collection = self._entries_collection(
            attendance_log_id
        )

        snapshot = collection.document(
            log_entry_id
        ).get()

        if not snapshot.exists:
            return None

        data = snapshot.to_dict() or {}

        return LogEntryRecord(
            log_entry_id=snapshot.id,
            **data,
        )

    def get_all(
        self,
        attendance_log_id: str,
    ) -> list[LogEntryRecord]:
        """직관 로그의 모든 Entry를 sequenceNo 순으로 조회합니다."""

        collection = self._entries_collection(
            attendance_log_id
        )

        entries: list[LogEntryRecord] = []

        for snapshot in collection.stream():
            data = snapshot.to_dict() or {}

            entries.append(
                LogEntryRecord(
                    log_entry_id=snapshot.id,
                    **data,
                )
            )

        return sorted(
            entries,
            key=lambda entry: entry.sequence_no,
        )

    def update(
        self,
        attendance_log_id: str,
        log_entry_id: str,
        updates: dict[str, Any],
    ) -> LogEntryRecord | None:
        """로그 Entry의 일부 필드를 수정합니다."""

        collection = self._entries_collection(
            attendance_log_id
        )

        document_reference = collection.document(
            log_entry_id
        )

        snapshot = document_reference.get()

        if not snapshot.exists:
            return None

        if updates:
            document_reference.update(
                updates
            )

        updated_snapshot = (
            document_reference.get()
        )

        data = updated_snapshot.to_dict() or {}

        return LogEntryRecord(
            log_entry_id=updated_snapshot.id,
            **data,
        )

    def delete(
        self,
        attendance_log_id: str,
        log_entry_id: str,
    ) -> bool:
        """
        로그 Entry를 실제 삭제합니다.

        ERD의 log_entries에는 deletedAt이 없으므로
        Soft Delete를 사용하지 않습니다.
        """

        collection = self._entries_collection(
            attendance_log_id
        )

        document_reference = collection.document(
            log_entry_id
        )

        snapshot = document_reference.get()

        if not snapshot.exists:
            return False

        document_reference.delete()

        return True

from datetime import datetime
from typing import Any

from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.client import Client

from app.core.firebase import get_firestore_client
from app.core.ids import new_prefixed_id
from app.schemas.attendance_log import (
    AttendanceLogDocument,
    AttendanceLogRecord,
    AttendanceLogStatus,
)


class AttendanceLogRepository:
    """Firestore attendanceLogs Collection 접근을 담당합니다."""

    COLLECTION_NAME = "attendanceLogs"

    def __init__(
        self,
        client: Client | None = None,
    ) -> None:
        self._client = client or get_firestore_client()
        self._collection = self._client.collection(
            self.COLLECTION_NAME
        )

    def create(
        self,
        log: AttendanceLogDocument,
    ) -> AttendanceLogRecord:
        """`log_` 접두사 ID로 직관 로그를 생성합니다."""

        document_reference = self._collection.document(
            new_prefixed_id("log")
        )

        document_reference.set(
            log.model_dump(
                by_alias=True,
                exclude_none=False,
            )
        )

        return AttendanceLogRecord(
            attendance_log_id=document_reference.id,
            **log.model_dump(),
        )

    def get_by_id(
        self,
        attendance_log_id: str,
        *,
        include_deleted: bool = False,
    ) -> AttendanceLogRecord | None:
        """직관 로그 ID로 문서를 조회합니다."""

        snapshot = self._collection.document(
            attendance_log_id
        ).get()

        if not snapshot.exists:
            return None

        data = snapshot.to_dict() or {}

        record = AttendanceLogRecord(
            attendance_log_id=snapshot.id,
            **data,
        )

        if (
            not include_deleted
            and record.deleted_at is not None
        ):
            return None

        return record

    def get_by_user_id(
        self,
        user_id: str,
    ) -> list[AttendanceLogRecord]:
        """사용자의 삭제되지 않은 직관 로그 목록을 조회합니다."""

        query = self._collection.where(
            filter=FieldFilter(
                "userId",
                "==",
                user_id,
            )
        )

        logs: list[AttendanceLogRecord] = []

        for snapshot in query.stream():
            data = snapshot.to_dict() or {}

            record = AttendanceLogRecord(
                attendance_log_id=snapshot.id,
                **data,
            )

            if record.deleted_at is not None:
                continue

            logs.append(record)

        return sorted(
            logs,
            key=lambda log: (
                log.created_at,
                log.attendance_log_id,
            ),
            reverse=True,
        )

    def soft_delete_all_by_user_id(
        self,
        user_id: str,
        *,
        deleted_at: datetime,
    ) -> int:
        """사용자의 활성 직관 로그를 모두 soft delete합니다."""

        logs = self.get_by_user_id(
            user_id
        )

        for log in logs:
            self._collection.document(
                log.attendance_log_id
            ).update(
                {
                    "logStatus": (
                        AttendanceLogStatus.ARCHIVED.value
                    ),
                    "updatedAt": deleted_at,
                    "deletedAt": deleted_at,
                }
            )

        return len(logs)

    def get_active_by_trip_id(
        self,
        trip_id: str,
    ) -> AttendanceLogRecord | None:
        """
        특정 여행에 연결된 삭제되지 않은 직관 로그를 조회합니다.

        여행당 로그 중복 생성 정책 검사에 사용합니다.
        """

        query = self._collection.where(
            filter=FieldFilter(
                "tripId",
                "==",
                trip_id,
            )
        )

        logs: list[AttendanceLogRecord] = []

        for snapshot in query.stream():
            data = snapshot.to_dict() or {}

            record = AttendanceLogRecord(
                attendance_log_id=snapshot.id,
                **data,
            )

            if record.deleted_at is None:
                logs.append(record)

        if not logs:
            return None

        return max(
            logs,
            key=lambda log: log.created_at,
        )

    def update(
        self,
        attendance_log_id: str,
        updates: dict[str, Any],
    ) -> AttendanceLogRecord | None:
        """직관 로그의 일부 필드를 수정합니다."""

        document_reference = self._collection.document(
            attendance_log_id
        )

        snapshot = document_reference.get()

        if not snapshot.exists:
            return None

        current_data = snapshot.to_dict() or {}

        current = AttendanceLogRecord(
            attendance_log_id=snapshot.id,
            **current_data,
        )

        if current.deleted_at is not None:
            return None

        if updates:
            document_reference.update(updates)

        updated_snapshot = document_reference.get()
        data = updated_snapshot.to_dict() or {}

        return AttendanceLogRecord(
            attendance_log_id=updated_snapshot.id,
            **data,
        )

    def soft_delete(
        self,
        attendance_log_id: str,
        *,
        deleted_at: datetime,
    ) -> bool:
        """직관 로그를 ARCHIVED 상태로 soft delete합니다."""

        document_reference = self._collection.document(
            attendance_log_id
        )

        snapshot = document_reference.get()

        if not snapshot.exists:
            return False

        data = snapshot.to_dict() or {}

        current = AttendanceLogRecord(
            attendance_log_id=snapshot.id,
            **data,
        )

        if current.deleted_at is not None:
            return False

        document_reference.update(
            {
                "logStatus": (
                    AttendanceLogStatus.ARCHIVED.value
                ),
                "updatedAt": deleted_at,
                "deletedAt": deleted_at,
            }
        )

        return True

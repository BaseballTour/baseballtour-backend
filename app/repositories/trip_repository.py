from datetime import datetime
from hashlib import sha256
from typing import Any

from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.client import Client
from google.cloud.firestore_v1.transaction import transactional

from app.core.firebase import get_firestore_client
from app.schemas.trip import (
    TripDocument,
    TripRecord,
    TripStatus,
)


class TripIdempotencyConflictError(Exception):
    """같은 Idempotency-Key가 다른 요청에 재사용된 경우."""


class TripRepository:
    """Firestore trips Collection 접근을 담당합니다."""

    COLLECTION_NAME = "trips"

    def __init__(self, client: Client | None = None) -> None:
        self._client = client or get_firestore_client()
        self._collection = self._client.collection(
            self.COLLECTION_NAME
        )

    def create(
        self,
        trip: TripDocument,
    ) -> TripRecord:
        """Firestore Auto ID를 사용해 여행을 생성합니다."""

        document_reference = self._collection.document()

        document_reference.set(
            trip.model_dump(
                by_alias=True,
                exclude_none=False,
            )
        )

        return TripRecord(
            trip_id=document_reference.id,
            **trip.model_dump(),
        )

    def create_idempotent(
        self,
        *,
        trip: TripDocument,
        idempotency_key: str,
    ) -> TripRecord:
        """
        Idempotency-Key 기준으로 여행을 원자적으로 생성합니다.

        같은 사용자와 같은 Key의 재요청은 기존 여행을 반환하고,
        같은 Key가 다른 요청 본문에 사용되면 충돌로 처리합니다.
        """

        key_source = (
            f"{trip.user_id}:{idempotency_key}"
        )
        key_hash = sha256(
            key_source.encode("utf-8")
        ).hexdigest()

        trip_id = f"trip_{key_hash}"
        document_reference = self._collection.document(
            trip_id
        )
        transaction = self._client.transaction()

        trip_data = trip.model_dump(
            by_alias=True,
            exclude_none=False,
        )

        @transactional
        def commit(transaction) -> TripRecord:
            snapshot = document_reference.get(
                transaction=transaction,
            )

            if snapshot.exists:
                data = snapshot.to_dict() or {}

                if (
                    data.get("idempotencyRequestHash")
                    != trip.idempotency_request_hash
                ):
                    raise TripIdempotencyConflictError()

                return TripRecord(
                    trip_id=snapshot.id,
                    **data,
                )

            transaction.set(
                document_reference,
                trip_data,
            )

            return TripRecord(
                trip_id=trip_id,
                **trip.model_dump(),
            )

        return commit(transaction)


    def get_by_id(
        self,
        trip_id: str,
    ) -> TripRecord | None:
        """여행 ID로 여행 문서를 조회합니다."""

        snapshot = self._collection.document(
            trip_id
        ).get()

        if not snapshot.exists:
            return None

        data = snapshot.to_dict() or {}

        return TripRecord(
            trip_id=snapshot.id,
            **data,
        )

    def get_by_user_id(
        self,
        user_id: str,
    ) -> list[TripRecord]:
        """특정 사용자의 여행 목록을 조회합니다."""

        query = (
            self._collection
            .where(
                filter=FieldFilter(
                    "userId",
                    "==",
                    user_id,
                )
            )
            .order_by(
                "createdAt",
                direction="DESCENDING",
            )
        )

        trips: list[TripRecord] = []

        for snapshot in query.stream():
            data = snapshot.to_dict() or {}

            trips.append(
                TripRecord(
                    trip_id=snapshot.id,
                    **data,
                )
            )

        return trips

    def claim_generation(
        self,
        *,
        trip_id: str,
        expected_status: TripStatus,
        updated_at: datetime,
    ) -> TripRecord | None:
        """
        일정 생성 권한을 원자적으로 획득합니다.

        현재 상태가 expected_status와 일치하는 경우에만
        GENERATING으로 변경합니다. 상태가 이미 변경된 경우
        None을 반환합니다.
        """

        document_reference = self._collection.document(
            trip_id
        )
        transaction = self._client.transaction()

        @transactional
        def commit(transaction) -> TripRecord | None:
            snapshot = document_reference.get(
                transaction=transaction,
            )

            if not snapshot.exists:
                return None

            data = snapshot.to_dict() or {}

            current = TripRecord(
                trip_id=snapshot.id,
                **data,
            )

            if current.status != expected_status:
                return None

            transaction.update(
                document_reference,
                {
                    "status": TripStatus.GENERATING.value,
                    "updatedAt": updated_at,
                },
            )

            return current.model_copy(
                update={
                    "status": TripStatus.GENERATING,
                    "updated_at": updated_at,
                }
            )

        return commit(transaction)


    def update(
        self,
        trip_id: str,
        updates: dict[str, Any],
    ) -> TripRecord | None:
        """여행 문서의 일부 필드를 수정합니다."""

        document_reference = self._collection.document(
            trip_id
        )
        snapshot = document_reference.get()

        if not snapshot.exists:
            return None

        if updates:
            document_reference.update(updates)

        updated_snapshot = document_reference.get()
        data = updated_snapshot.to_dict() or {}

        return TripRecord(
            trip_id=updated_snapshot.id,
            **data,
        )

    def delete(
        self,
        trip_id: str,
    ) -> bool:
        """여행 문서를 삭제합니다."""

        document_reference = self._collection.document(
            trip_id
        )
        snapshot = document_reference.get()

        if not snapshot.exists:
            return False

        document_reference.delete()

        return True

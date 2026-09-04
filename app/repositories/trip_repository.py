from datetime import datetime
from hashlib import sha256
import logging
from typing import Any

from google.cloud.exceptions import NotFound
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.client import Client
from google.cloud.firestore_v1.transaction import transactional
from pydantic import ValidationError

from app.core.firebase import get_firestore_client
from app.schemas.trip import (
    TripDocument,
    TripRecord,
    TripStatus,
)


logger = logging.getLogger(__name__)


class TripIdempotencyConflictError(Exception):
    """같은 Idempotency-Key가 다른 요청에 재사용된 경우."""


class TripRepository:
    """Firestore trips Collection 접근을 담당합니다."""

    COLLECTION_NAME = "trips"

    @staticmethod
    def _to_record(*, trip_id: str, data: dict[str, Any]) -> TripRecord:
        """Firestore 여행 문서를 검증하고 실패 위치를 진단 로그에 남깁니다."""

        normalized_data = dict(data)
        raw_status = normalized_data.get("status")
        if raw_status == "ACTIVE":
            # 초기 스키마에서 Plan의 ACTIVE 상태가 Trip 문서에도 저장된
            # 데이터와의 읽기 호환성. 활성 일정이 있으면 생성 완료,
            # 없으면 계획 중으로 해석합니다.
            normalized_status = (
                TripStatus.GENERATED.value
                if normalized_data.get("activePlanId")
                else TripStatus.PLANNING.value
            )
            logger.warning(
                "기존 여행 상태값을 정규화합니다: trip_id=%s "
                "legacy_status=%s normalized_status=%s",
                trip_id,
                raw_status,
                normalized_status,
            )
            normalized_data["status"] = normalized_status

        try:
            return TripRecord(
                trip_id=trip_id,
                **normalized_data,
            )
        except ValidationError as error:
            logger.error(
                "여행 문서 모델 검증 실패: trip_id=%s raw_status=%r "
                "errors=%s",
                trip_id,
                raw_status,
                error.errors(include_input=False),
            )
            raise

    def __init__(self, client: Client | None = None) -> None:
        self._client = client or get_firestore_client()
        self._collection = self._client.collection(
            self.COLLECTION_NAME
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

                return self._to_record(
                    trip_id=snapshot.id,
                    data=data,
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

        return self._to_record(
            trip_id=snapshot.id,
            data=data,
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
                self._to_record(
                    trip_id=snapshot.id,
                    data=data,
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

            current = self._to_record(
                trip_id=snapshot.id,
                data=data,
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


    def recover_stale_generation(
        self,
        *,
        trip_id: str,
        stale_before: datetime,
        updated_at: datetime,
    ) -> TripRecord | None:
        """오래 멈춘 GENERATING 상태를 원자적으로 이전 정상 상태로 복구합니다."""

        document_reference = self._collection.document(trip_id)
        transaction = self._client.transaction()

        @transactional
        def commit(transaction) -> TripRecord | None:
            snapshot = document_reference.get(transaction=transaction)
            if not snapshot.exists:
                return None

            data = snapshot.to_dict() or {}
            current = self._to_record(trip_id=snapshot.id, data=data)
            if (
                current.status != TripStatus.GENERATING
                or current.updated_at > stale_before
            ):
                return current

            restored_status = (
                TripStatus.GENERATED
                if current.active_plan_id
                else TripStatus.PLANNING
            )
            transaction.update(
                document_reference,
                {
                    "status": restored_status.value,
                    "updatedAt": updated_at,
                },
            )
            return current.model_copy(
                update={
                    "status": restored_status,
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
        try:
            if updates:
                document_reference.update(updates)
        except NotFound:
            return None

        updated_snapshot = document_reference.get()
        data = updated_snapshot.to_dict() or {}

        return TripRecord(
            trip_id=updated_snapshot.id,
            **data,
        )

    def delete(
        self,
        trip_id: str,
    ) -> None:
        """여행 문서를 삭제합니다."""

        self._collection.document(
            trip_id
        ).delete()

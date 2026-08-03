from typing import Any

from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.client import Client

from app.core.firebase import get_firestore_client
from app.schemas.trip import TripDocument, TripRecord


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

        query = self._collection.where(
            filter=FieldFilter(
                "userId",
                "==",
                user_id,
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

        return sorted(
            trips,
            key=lambda trip: trip.created_at,
            reverse=True,
        )

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

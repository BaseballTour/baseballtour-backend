from google.api_core.exceptions import AlreadyExists
from google.cloud.firestore_v1.client import Client

from app.core.firebase import get_firestore_client
from app.schemas.place_selection import (
    PlaceSelectionDocument,
    PlaceSelectionRecord,
)


class PlaceSelectionRepository:
    """Trip 하위 장소 선택 subcollection 접근을 담당합니다."""

    COLLECTION_NAME = "placeSelections"

    def __init__(
        self,
        client: Client | None = None,
    ) -> None:
        self._client = client or get_firestore_client()

    def _get_collection(
        self,
        trip_id: str,
    ):
        return (
            self._client
            .collection("trips")
            .document(trip_id)
            .collection(self.COLLECTION_NAME)
        )

    def create(
        self,
        *,
        trip_id: str,
        selection: PlaceSelectionDocument,
    ) -> PlaceSelectionRecord | None:
        """
        장소 선택을 생성합니다.

        placeId를 Firestore 문서 ID로 사용하며,
        이미 존재하면 None을 반환합니다.
        """

        document_reference = (
            self._get_collection(trip_id)
            .document(selection.place_id)
        )

        try:
            document_reference.create(
                selection.model_dump(
                    by_alias=True,
                    exclude_none=False,
                )
            )
        except AlreadyExists:
            return None

        return PlaceSelectionRecord(
            **selection.model_dump()
        )

    def get_all(
        self,
        *,
        trip_id: str,
    ) -> list[PlaceSelectionRecord]:
        """Trip에 선택된 모든 장소를 조회합니다."""

        selections: list[PlaceSelectionRecord] = []

        for snapshot in self._get_collection(
            trip_id
        ).stream():
            data = snapshot.to_dict() or {}

            selections.append(
                PlaceSelectionRecord.model_validate(
                    data
                )
            )

        return sorted(
            selections,
            key=lambda selection: selection.created_at,
        )

    def delete_all(
        self,
        *,
        trip_id: str,
    ) -> int:
        """Trip에 속한 모든 장소 선택을 삭제합니다."""

        collection = self._get_collection(trip_id)
        snapshots = list(collection.stream())

        for snapshot in snapshots:
            collection.document(snapshot.id).delete()

        return len(snapshots)

    def delete(
        self,
        *,
        trip_id: str,
        place_id: str,
    ) -> bool:
        """선택된 장소를 삭제합니다."""

        document_reference = (
            self._get_collection(trip_id)
            .document(place_id)
        )

        snapshot = document_reference.get()

        if not snapshot.exists:
            return False

        document_reference.delete()

        return True

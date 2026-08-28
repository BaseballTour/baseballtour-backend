from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.client import Client

from app.core.firebase import get_firestore_client
from app.schemas.player_pick import PlayerPickRecord


class PlayerPickRepository:
    """구장·선수별 TourAPI 장소 큐레이션 조회."""

    COLLECTION_NAME = "playerPlaceRecommendations"

    def __init__(self, client: Client | None = None) -> None:
        self._client = client or get_firestore_client()
        self._collection = self._client.collection(self.COLLECTION_NAME)

    def get_all(
        self,
        *,
        stadium_id: str,
        player_name: str | None = None,
    ) -> list[PlayerPickRecord]:
        query = self._collection.where(
            filter=FieldFilter("stadiumId", "==", stadium_id)
        )
        records = [
            PlayerPickRecord(
                player_pick_id=snapshot.id,
                **(snapshot.to_dict() or {}),
            )
            for snapshot in query.stream()
        ]
        if player_name is not None:
            records = [
                record
                for record in records
                if record.player_name == player_name
            ]
        return sorted(
            records,
            key=lambda record: (record.player_name, record.created_at),
        )

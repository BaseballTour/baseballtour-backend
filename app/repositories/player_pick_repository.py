from hashlib import sha256

from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.client import Client

from app.core.firebase import get_firestore_client
from app.schemas.player_pick import PlayerPickDocument, PlayerPickRecord


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

    def get_by_id(self, player_pick_id: str) -> PlayerPickRecord | None:
        snapshot = self._collection.document(player_pick_id).get()
        if not snapshot.exists:
            return None
        return PlayerPickRecord(
            player_pick_id=snapshot.id,
            **(snapshot.to_dict() or {}),
        )

    def get_missing_snapshot_ids(self) -> list[str]:
        """운영 조회에 사용할 장소 snapshot이 없는 문서 ID를 반환합니다."""
        return sorted(
            snapshot.id
            for snapshot in self._collection.stream()
            if not (snapshot.to_dict() or {}).get("placeSnapshot")
        )

    def upsert(self, document: PlayerPickDocument) -> PlayerPickRecord:
        """구장·선수·장소 조합을 중복 없이 저장합니다."""

        if document.place_snapshot is None:
            raise ValueError("선수 추천 장소에는 placeSnapshot이 필요합니다.")

        identity = ":".join(
            (
                document.stadium_id,
                document.player_name,
                document.curation_key or document.place_id,
            )
        )
        digest = sha256(identity.encode("utf-8")).hexdigest()[:24]
        player_pick_id = f"player_pick_{digest}"
        reference = self._collection.document(player_pick_id)
        existing = reference.get()
        created_at = document.created_at
        if existing.exists:
            existing_data = existing.to_dict() or {}
            created_at = existing_data.get("createdAt", created_at)
        stored = document.model_copy(update={"created_at": created_at})
        reference.set(
            stored.model_dump(by_alias=True, exclude_none=False),
            merge=True,
        )
        return PlayerPickRecord(
            player_pick_id=player_pick_id,
            **stored.model_dump(),
        )

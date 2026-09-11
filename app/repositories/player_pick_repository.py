from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.client import Client

from app.core.firebase import get_firestore_client
from app.schemas.player_pick import PlayerPickDocument, PlayerPickRecord


class PlayerPickRepository:
    """구장·선수별 독립 큐레이션과 Kakao 연결 ID를 저장합니다."""

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
        records = [self._to_record(snapshot) for snapshot in query.stream()]
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
        return self._to_record(snapshot)

    @staticmethod
    def build_id(document: PlayerPickDocument) -> str:
        identity = ":".join(
            (
                document.stadium_id,
                document.player_name,
                document.place_name,
                document.address,
            )
        )
        digest = sha256(identity.encode("utf-8")).hexdigest()[:24]
        return f"player_pick_{digest}"

    @staticmethod
    def _to_record(snapshot) -> PlayerPickRecord:
        """마이그레이션 전 placeSnapshot 문서도 무중단으로 읽습니다."""
        data = snapshot.to_dict() or {}
        legacy = data.get("placeSnapshot") or {}
        clean = {
            "stadiumId": data.get("stadiumId"),
            "playerName": data.get("playerName"),
            "playerPosition": data.get("playerPosition"),
            "placeName": data.get("placeName") or legacy.get("name"),
            "address": data.get("address") or legacy.get("address") or "",
            "category": data.get("category") or legacy.get("category") or "RESTAURANT",
            "kakaoPlaceId": (
                data.get("kakaoPlaceId")
                or legacy.get("kakaoPlaceId")
                or (
                    str(data.get("placeId")).removeprefix("kakao_")
                    if str(data.get("placeId") or "").startswith("kakao_")
                    else None
                )
            ),
            "recommendationNote": data.get("recommendationNote"),
            "createdAt": data.get("createdAt"),
            "updatedAt": data.get("updatedAt"),
        }
        return PlayerPickRecord(player_pick_id=snapshot.id, **clean)

    def get_missing_kakao_link_ids(self) -> list[str]:
        """실시간 장소 조회에 필요한 Kakao 장소 ID가 없는 문서를 반환합니다."""
        return sorted(
            snapshot.id
            for snapshot in self._collection.stream()
            if not (snapshot.to_dict() or {}).get("kakaoPlaceId")
        )

    def upsert(
        self,
        player_pick_id: str,
        document: PlayerPickDocument,
    ) -> PlayerPickRecord:
        """선수 추천 문서를 허용 필드만 남겨 통째로 교체합니다."""

        if not player_pick_id.startswith("player_pick_"):
            raise ValueError("선수 추천 장소 ID는 player_pick_ 접두사가 필요합니다.")
        reference = self._collection.document(player_pick_id)
        existing = reference.get()
        created_at = document.created_at
        if existing.exists:
            existing_data = existing.to_dict() or {}
            created_at = existing_data.get("createdAt", created_at)
        stored = document.model_copy(update={"created_at": created_at})
        # merge=False로 과거 placeSnapshot, 좌표, 전화번호 등 금지 필드를 제거한다.
        reference.set(stored.model_dump(by_alias=True, exclude_none=False))
        return PlayerPickRecord(
            player_pick_id=player_pick_id,
            **stored.model_dump(),
        )
from hashlib import sha256

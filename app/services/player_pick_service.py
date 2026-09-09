import logging

from app.repositories.player_pick_repository import PlayerPickRepository
from app.models.place import Place
from app.schemas.player_pick import PlayerPickRecord, PlayerPickResponse


logger = logging.getLogger(__name__)


class PlayerPickService:
    """Firestore에 확정해 둔 선수 추천 장소 snapshot만 조회합니다."""

    def __init__(
        self,
        repository: PlayerPickRepository | None = None,
    ) -> None:
        self._repository = repository or PlayerPickRepository()

    async def resolve_place(self, player_pick_id: str) -> Place | None:
        record = self._repository.get_by_id(player_pick_id)
        if record is None:
            return None
        place = self._resolve_record_place(record)
        return self._tag_place(record, place) if place is not None else None

    async def get_places_for_stadium(self, stadium_id: str) -> list[Place]:
        records = self._repository.get_all(stadium_id=stadium_id)
        places = [self._resolve_record_place(record) for record in records]
        return [
            self._tag_place(record, place)
            for record, place in zip(records, places, strict=True)
            if place is not None
        ]

    def _resolve_record_place(
        self, record: PlayerPickRecord
    ) -> Place | None:
        if record.place_snapshot is not None:
            return record.place_snapshot
        logger.error(
            "선수추천 장소 snapshot 누락: player_pick_id=%s place_id=%s",
            record.player_pick_id,
            record.place_id,
        )
        return None

    @staticmethod
    def _tag_place(record: PlayerPickRecord, place: Place) -> Place:
        return place.model_copy(
            update={
                "place_id": record.player_pick_id,
                "is_player_pick": True,
                "player_pick_id": record.player_pick_id,
                "recommended_by_players": [record.player_name],
                "recommendation_note": record.recommendation_note,
            }
        )

    async def get_player_picks(
        self,
        *,
        stadium_id: str,
        player_name: str | None = None,
    ) -> list[PlayerPickResponse]:
        records = self._repository.get_all(
            stadium_id=stadium_id,
            player_name=player_name,
        )
        places = [self._resolve_record_place(record) for record in records]
        responses: list[PlayerPickResponse] = []
        for record, place in zip(records, places, strict=True):
            if place is None:
                continue
            responses.append(
                PlayerPickResponse(
                    player_pick_id=record.player_pick_id,
                    stadium_id=record.stadium_id,
                    player_name=record.player_name,
                    player_position=record.player_position,
                    place=place,
                    recommendation_note=record.recommendation_note,
                )
            )
        return responses

import asyncio
import logging
from typing import Any, Awaitable, Callable

from app.external.kakao.client import search_place_page
from app.external.kakao.mapper import kakao_address
from app.repositories.player_pick_repository import PlayerPickRepository
from app.models.place import Place, PlaceSource
from app.schemas.player_pick import PlayerPickRecord, PlayerPickResponse


logger = logging.getLogger(__name__)


class PlayerPickService:
    """큐레이션 정보에 Kakao의 최신 장소 응답을 일시 결합합니다."""

    def __init__(
        self,
        repository: PlayerPickRepository | None = None,
        searcher: Callable[..., Awaitable[Any]] = search_place_page,
    ) -> None:
        self._repository = repository or PlayerPickRepository()
        self._searcher = searcher
        self._lookup_semaphore = asyncio.Semaphore(5)

    async def resolve_place(self, player_pick_id: str) -> Place | None:
        record = self._repository.get_by_id(player_pick_id)
        if record is None:
            return None
        place = await self._resolve_record_place(record)
        return self._tag_place(record, place) if place is not None else None

    async def get_places_for_stadium(self, stadium_id: str) -> list[Place]:
        records = self._repository.get_all(stadium_id=stadium_id)
        places = await asyncio.gather(
            *(self._resolve_record_place(record) for record in records)
        )
        return [
            self._tag_place(record, place)
            for record, place in zip(records, places, strict=True)
            if place is not None
        ]

    async def _resolve_record_place(
        self, record: PlayerPickRecord
    ) -> Place | None:
        if not record.kakao_place_id:
            logger.warning(
                "선수추천 장소 Kakao 연결 누락: player_pick_id=%s name=%s",
                record.player_pick_id,
                record.place_name,
            )
            return None
        try:
            async with self._lookup_semaphore:
                page = await self._searcher(record.place_name, size=15)
        except Exception as error:
            logger.warning(
                "선수추천 장소 실시간 조회 실패: player_pick_id=%s "
                "error_type=%s",
                record.player_pick_id,
                type(error).__name__,
            )
            return None
        item = next(
            (
                candidate
                for candidate in page.documents
                if str(candidate.get("id") or "") == record.kakao_place_id
            ),
            None,
        )
        if item is None:
            logger.warning(
                "선수추천 Kakao 장소 ID 불일치: player_pick_id=%s "
                "kakao_place_id=%s",
                record.player_pick_id,
                record.kakao_place_id,
            )
            return None
        try:
            return Place(
                place_id=record.player_pick_id,
                name=record.place_name,
                category=record.category,
                latitude=round(float(item.get("y")), 6),
                longitude=round(float(item.get("x")), 6),
                address=record.address or kakao_address(item),
                telephone=str(item.get("phone") or "").strip() or None,
                place_url=str(item.get("place_url") or "").strip() or None,
                source=PlaceSource.LOCAL_DATA,
                kakao_place_id=record.kakao_place_id,
                enriched_by=[PlaceSource.KAKAO],
            )
        except (TypeError, ValueError):
            logger.warning(
                "선수추천 Kakao 좌표 오류: player_pick_id=%s",
                record.player_pick_id,
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
        places = await asyncio.gather(
            *(self._resolve_record_place(record) for record in records)
        )
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
                    place=self._tag_place(record, place),
                    recommendation_note=record.recommendation_note,
                )
            )
        return responses

import asyncio
import logging

from app.external.tour_api.adapter import TourApiAdapter, tour_api_adapter
from app.repositories.player_pick_repository import PlayerPickRepository
from app.schemas.player_pick import PlayerPickResponse


logger = logging.getLogger(__name__)
DETAIL_CONCURRENCY = 5


class PlayerPickService:
    """DB 큐레이션과 TourAPI 장소 상세를 결합합니다."""

    def __init__(
        self,
        repository: PlayerPickRepository | None = None,
        place_adapter: TourApiAdapter | None = None,
    ) -> None:
        self._repository = repository or PlayerPickRepository()
        self._place_adapter = place_adapter or tour_api_adapter

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
        semaphore = asyncio.Semaphore(DETAIL_CONCURRENCY)

        async def resolve(record):
            if record.place_snapshot is not None:
                return record.place_snapshot
            try:
                async with semaphore:
                    return await self._place_adapter.get_place_detail(
                        record.place_id.removeprefix("tour_")
                    )
            except Exception as exc:
                logger.warning(
                    "선수추천 장소 상세 조회 실패: player_pick_id=%s "
                    "place_id=%s reason=%s",
                    record.player_pick_id,
                    record.place_id,
                    type(exc).__name__,
                )
                return None

        places = await asyncio.gather(*(resolve(record) for record in records))
        responses: list[PlayerPickResponse] = []
        for record, place in zip(records, places, strict=True):
            if place is None:
                continue
            responses.append(
                PlayerPickResponse(
                    player_pick_id=record.player_pick_id,
                    stadium_id=record.stadium_id,
                    player_name=record.player_name,
                    place=place,
                    recommendation_note=record.recommendation_note,
                )
            )
        return responses

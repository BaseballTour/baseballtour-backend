import asyncio

from app.external.tour_api.adapter import TourApiAdapter, tour_api_adapter
from app.repositories.player_pick_repository import PlayerPickRepository
from app.schemas.player_pick import PlayerPickResponse


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
        places = await asyncio.gather(
            *(
                self._place_adapter.get_place_detail(
                    record.place_id.removeprefix("tour_")
                )
                for record in records
            )
        )
        return [
            PlayerPickResponse(
                player_pick_id=record.player_pick_id,
                stadium_id=record.stadium_id,
                player_name=record.player_name,
                place=place,
            )
            for record, place in zip(records, places, strict=True)
        ]

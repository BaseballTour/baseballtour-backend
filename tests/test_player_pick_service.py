import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from app.models.place import Place, PlaceCategory, PlaceSource
from app.schemas.player_pick import PlayerPickRecord
from app.services.player_pick_service import PlayerPickService


def make_place() -> Place:
    return Place(
        place_id="tour_123456",
        name="테스트 음식점",
        category=PlaceCategory.RESTAURANT,
        latitude=37.5,
        longitude=126.8,
        address="서울특별시 구로구",
        source=PlaceSource.TOUR_API,
        source_content_id="123456",
    )


class FakePlayerPickRepository:
    def get_all(self, *, stadium_id: str, player_name: str | None = None):
        assert stadium_id == "gocheok"
        assert player_name == "테스트 선수"
        return [
            PlayerPickRecord(
                player_pick_id="player_pick_001",
                stadium_id=stadium_id,
                player_name=player_name,
                place_id="tour_123456",
                created_at=datetime.now(ZoneInfo("Asia/Seoul")),
            )
        ]


class FakeTourApiAdapter:
    async def get_place_detail(self, content_id: str):
        assert content_id == "123456"
        return make_place()


class FailingTourApiAdapter:
    async def get_place_detail(self, content_id: str):
        raise RuntimeError("TourAPI unavailable")


def test_player_pick_service_combines_db_mapping_and_place_detail() -> None:
    service = PlayerPickService(
        repository=FakePlayerPickRepository(),
        place_adapter=FakeTourApiAdapter(),
    )

    [result] = asyncio.run(
        service.get_player_picks(
            stadium_id="gocheok",
            player_name="테스트 선수",
        )
    )

    assert result.player_pick_id == "player_pick_001"
    assert result.place.place_id == "tour_123456"


def test_player_pick_service_uses_saved_snapshot_without_external_call() -> None:
    class SnapshotRepository(FakePlayerPickRepository):
        def get_all(self, *, stadium_id: str, player_name: str | None = None):
            [record] = super().get_all(
                stadium_id=stadium_id,
                player_name=player_name,
            )
            return [record.model_copy(update={"place_snapshot": make_place()})]

    service = PlayerPickService(
        repository=SnapshotRepository(),
        place_adapter=FailingTourApiAdapter(),
    )
    [result] = asyncio.run(
        service.get_player_picks(
            stadium_id="gocheok",
            player_name="테스트 선수",
        )
    )
    assert result.place.name == "테스트 음식점"


def test_player_pick_service_omits_only_failed_legacy_place() -> None:
    service = PlayerPickService(
        repository=FakePlayerPickRepository(),
        place_adapter=FailingTourApiAdapter(),
    )
    result = asyncio.run(
        service.get_player_picks(
            stadium_id="gocheok",
            player_name="테스트 선수",
        )
    )
    assert result == []

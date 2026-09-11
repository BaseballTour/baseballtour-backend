import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from app.external.kakao.client import KakaoPlacePage
from app.schemas.player_pick import PlayerPickRecord
from app.services.player_pick_service import PlayerPickService


def make_record(kakao_place_id: str | None = "123") -> PlayerPickRecord:
    return PlayerPickRecord(
        player_pick_id="player_pick_001",
        stadium_id="gocheok",
        player_name="테스트 선수",
        player_position="INFIELDER",
        place_name="테스트 음식점",
        address="서울특별시 구로구 테스트로 1",
        category="RESTAURANT",
        kakao_place_id=kakao_place_id,
        created_at=datetime.now(ZoneInfo("Asia/Seoul")),
    )


class FakeRepository:
    def get_all(self, *, stadium_id: str, player_name: str | None = None):
        return [make_record()]

    def get_by_id(self, player_pick_id: str):
        return make_record() if player_pick_id == "player_pick_001" else None


async def fake_searcher(query: str, **kwargs):
    assert query == "테스트 음식점"
    return KakaoPlacePage(
        documents=[{
            "id": "123", "place_name": query,
            "road_address_name": "서울특별시 구로구 테스트로 1",
            "address_name": "서울특별시 구로구",
            "x": "126.81234567", "y": "37.51234567",
            "phone": "02-123-4567",
            "place_url": "https://place.map.kakao.com/123",
        }],
        is_end=True,
    )


def test_player_pick_service_resolves_kakao_live_without_hours() -> None:
    service = PlayerPickService(repository=FakeRepository(), searcher=fake_searcher)
    [result] = asyncio.run(service.get_player_picks(stadium_id="gocheok"))

    assert result.place.place_id == "player_pick_001"
    assert result.place.latitude == 37.512346
    assert result.place.telephone == "02-123-4567"
    assert result.place.business_hours_status == "MISSING"
    assert result.place.business_hours_rules == []
    assert result.place.is_player_pick is True


def test_player_pick_service_omits_unlinked_record() -> None:
    class UnlinkedRepository(FakeRepository):
        def get_all(self, **kwargs):
            return [make_record(None)]

    service = PlayerPickService(repository=UnlinkedRepository(), searcher=fake_searcher)
    assert asyncio.run(service.get_player_picks(stadium_id="gocheok")) == []


def test_resolve_place_uses_player_pick_as_canonical_id() -> None:
    service = PlayerPickService(repository=FakeRepository(), searcher=fake_searcher)
    place = asyncio.run(service.resolve_place("player_pick_001"))
    assert place is not None
    assert place.player_pick_id == place.place_id == "player_pick_001"
    assert place.recommended_by_players == ["테스트 선수"]

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


def test_player_pick_service_matches_name_and_address_without_kakao_id() -> None:
    class UnlinkedRepository(FakeRepository):
        def get_all(self, **kwargs):
            return [make_record(None)]

    service = PlayerPickService(repository=UnlinkedRepository(), searcher=fake_searcher)
    [result] = asyncio.run(service.get_player_picks(stadium_id="gocheok"))
    assert result.place.name == "테스트 음식점"
    assert result.place.kakao_place_id == "123"


def test_player_pick_service_geocodes_address_as_last_fallback() -> None:
    class UnlinkedRepository(FakeRepository):
        def get_all(self, **kwargs):
            return [make_record(None)]

    async def empty_searcher(query: str, **kwargs):
        return KakaoPlacePage(documents=[], is_end=True)

    async def fake_geocoder(address: str):
        assert address == "서울특별시 구로구 테스트로 1"
        return [{"x": "126.8", "y": "37.5"}]

    service = PlayerPickService(
        repository=UnlinkedRepository(),
        searcher=empty_searcher,
        geocoder=fake_geocoder,
    )
    [result] = asyncio.run(service.get_player_picks(stadium_id="gocheok"))
    assert result.place.latitude == 37.5
    assert result.place.kakao_place_id is None
    assert result.place.telephone is None


def test_resolve_place_uses_player_pick_as_canonical_id() -> None:
    service = PlayerPickService(repository=FakeRepository(), searcher=fake_searcher)
    place = asyncio.run(service.resolve_place("player_pick_001"))
    assert place is not None
    assert place.player_pick_id == place.place_id == "player_pick_001"
    assert place.recommended_by_players == ["테스트 선수"]


def test_player_pick_response_exposes_recommendation_source() -> None:
    verified_at = datetime.now(ZoneInfo("Asia/Seoul"))
    record = make_record().model_copy(
        update={
            "recommendation_evidence_status": "VERIFIED",
            "recommendation_source_url": (
                "https://www.youtube.com/watch?v=source"
            ),
            "recommendation_source_title": "선수 추천 맛집",
            "recommendation_source_publisher": "구단 공식 채널",
            "recommendation_verified_at": verified_at,
        }
    )

    class SourceRepository(FakeRepository):
        def get_all(self, **kwargs):
            return [record]

    service = PlayerPickService(
        repository=SourceRepository(),
        searcher=fake_searcher,
    )
    [result] = asyncio.run(service.get_player_picks(stadium_id="gocheok"))

    assert result.recommendation_evidence_status == "VERIFIED"
    assert result.recommendation_source_url.endswith("watch?v=source")
    assert result.recommendation_source_title == "선수 추천 맛집"
    assert result.recommendation_source_publisher == "구단 공식 채널"
    assert result.recommendation_verified_at == verified_at


def test_stadium_places_merge_aliases_resolved_to_same_kakao_place() -> None:
    first = make_record().model_copy(
        update={
            "player_name": "LG 전체 선수",
            "place_name": "잠실고박사",
            "address": "서울 송파구 백제고분로7길 8",
        }
    )
    second = make_record().model_copy(
        update={
            "player_pick_id": "player_pick_002",
            "player_name": "천성호",
            "place_name": "고박사 잠실새내점",
            "address": "서울 송파구 백제고분로7길 8",
        }
    )

    class DuplicateRepository(FakeRepository):
        def get_all(self, **kwargs):
            return [first, second]

    async def duplicate_searcher(query: str, **kwargs):
        return KakaoPlacePage(
            documents=[{
                "id": "123",
                "place_name": query,
                "road_address_name": "서울 송파구 백제고분로7길 8",
                "address_name": "서울 송파구 잠실동",
                "x": "127.081234",
                "y": "37.511234",
                "phone": "02-123-4567",
                "place_url": "https://place.map.kakao.com/123",
            }],
            is_end=True,
        )

    service = PlayerPickService(
        repository=DuplicateRepository(),
        searcher=duplicate_searcher,
    )
    places = asyncio.run(service.get_places_for_stadium("jamsil"))

    assert len(places) == 1
    assert places[0].name == "잠실고박사"
    assert places[0].recommended_by_players == ["LG 전체 선수", "천성호"]


def test_stadium_places_merge_same_location_when_one_kakao_id_is_missing() -> None:
    first = make_record().model_copy(
        update={"player_name": "LG 전체 선수"}
    )
    second = make_record(None).model_copy(
        update={
            "player_pick_id": "player_pick_002",
            "player_name": "천성호",
            "place_name": "고박사 잠실새내점",
        }
    )

    class DuplicateRepository(FakeRepository):
        def get_all(self, **kwargs):
            return [first, second]

    async def mixed_searcher(query: str, **kwargs):
        if query == "고박사 잠실새내점":
            return KakaoPlacePage(documents=[], is_end=True)
        return await fake_searcher(query, **kwargs)

    async def same_location_geocoder(address: str):
        return [{"x": "126.81234567", "y": "37.51234567"}]

    service = PlayerPickService(
        repository=DuplicateRepository(),
        searcher=mixed_searcher,
        geocoder=same_location_geocoder,
    )
    places = asyncio.run(service.get_places_for_stadium("jamsil"))

    assert len(places) == 1
    assert places[0].recommended_by_players == ["LG 전체 선수", "천성호"]

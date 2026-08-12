import httpx
import pytest

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.external.kakao.client import search_places_by_keyword
from app.models.place import Place, PlaceCategory, PlaceSource
from app.services.place_enrichment import enrich_place_with_kakao


def make_place(**updates) -> Place:
    values = {
        "place_id": "tour_1603175",
        "name": "아시아공원",
        "category": PlaceCategory.TOURIST_SPOT,
        "latitude": 37.510082,
        "longitude": 127.076703,
        "address": "",
        "telephone": None,
        "source": PlaceSource.TOUR_API,
        "source_content_id": "1603175",
    }
    values.update(updates)
    return Place(**values)


@pytest.mark.anyio
async def test_enrichment_fills_only_missing_fields() -> None:
    async def fake_searcher(*args, **kwargs):
        return [{
            "id": "98765",
            "place_name": "아시아공원",
            "road_address_name": "서울 송파구 올림픽로 44",
            "address_name": "서울 송파구 잠실동 10",
            "phone": "02-123-4567",
            "category_group_code": "AT4",
            "x": "127.07670",
            "y": "37.51008",
        }]

    result = await enrich_place_with_kakao(
        make_place(),
        searcher=fake_searcher,
    )

    assert result.place_id == "tour_1603175"
    assert result.source == PlaceSource.TOUR_API
    assert result.address == "서울 송파구 올림픽로 44"
    assert result.telephone == "02-123-4567"
    assert result.kakao_place_id == "98765"
    assert result.enriched_by == [PlaceSource.KAKAO]


@pytest.mark.anyio
async def test_enrichment_rejects_distant_same_name() -> None:
    async def fake_searcher(*args, **kwargs):
        return [{
            "id": "98765",
            "place_name": "아시아공원",
            "road_address_name": "부산광역시 중구",
            "phone": "051-123-4567",
            "category_group_code": "AT4",
            "x": "129.0",
            "y": "35.1",
        }]

    original = make_place()
    result = await enrich_place_with_kakao(
        original,
        searcher=fake_searcher,
    )

    assert result == original


@pytest.mark.anyio
async def test_kakao_client_sends_rest_key(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "kakao_rest_api_key", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "KakaoAK test-key"
        assert request.url.params["query"] == "아시아공원"
        return httpx.Response(200, json={"documents": []})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        result = await search_places_by_keyword(
            "아시아공원",
            longitude=127.0767,
            latitude=37.51008,
            client=client,
        )

    assert result == []


@pytest.mark.anyio
async def test_kakao_client_explains_disabled_map_api(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "kakao_rest_api_key", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={
                "errorType": "NotAuthorizedError",
                "message": (
                    "App(test) disabled OPEN_MAP_AND_LOCAL service."
                ),
            },
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(AppException) as caught:
            await search_places_by_keyword(
                "아시아공원",
                longitude=127.0767,
                latitude=37.51008,
                client=client,
            )

    assert caught.value.code == "KAKAO_LOCAL_API_NOT_ENABLED"

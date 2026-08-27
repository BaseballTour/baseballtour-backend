import httpx
import pytest

from app.core.config import get_settings
from app.external.kakao.client import reverse_geocode, search_place_page


@pytest.mark.anyio
async def test_accommodation_search_sends_ad5_and_pagination(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "kakao_rest_api_key", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/search/keyword.json")
        assert request.url.params["category_group_code"] == "AD5"
        assert request.url.params["page"] == "2"
        assert request.url.params["size"] == "10"
        return httpx.Response(
            200,
            json={"documents": [], "meta": {"is_end": False}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await search_place_page(
            "잠실 호텔",
            longitude=127.1,
            latitude=37.5,
            category_group_code="AD5",
            page=2,
            size=10,
            client=client,
        )

    assert result.documents == []
    assert result.is_end is False


@pytest.mark.anyio
async def test_reverse_geocode_sends_wgs84_coordinates(monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "kakao_rest_api_key", "test-key")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/geo/coord2address.json")
        assert request.url.params["x"] == "127.1"
        assert request.url.params["y"] == "37.5"
        assert request.url.params["input_coord"] == "WGS84"
        return httpx.Response(200, json={"documents": [{"address": {}}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await reverse_geocode(
            longitude=127.1,
            latitude=37.5,
            client=client,
        )

    assert result == [{"address": {}}]

import pytest

from app.external.tour_api import adapter as adapter_module
from app.external.tour_api.adapter import TourApiAdapter


def response_with(item):
    return {
        "response": {
            "body": {
                "items": {"item": item},
            }
        }
    }


@pytest.mark.anyio
async def test_detail_combines_common_intro_and_image(monkeypatch) -> None:
    calls = {"common": 0, "intro_content_type_id": None}

    async def common(*args, **kwargs):
        calls["common"] += 1
        return response_with(
            {
                "contentid": "123",
                "contenttypeid": "39",
                "title": "테스트 식당",
                "mapx": "127.0",
                "mapy": "37.5",
                "addr1": "서울특별시",
                "overview": "상세 소개",
                "firstimage": "",
            }
        )

    async def intro(*args, **kwargs):
        calls["intro_content_type_id"] = args[1]
        return response_with(
            {
                "opentimefood": "10:00~22:00",
                "restdatefood": "매주 월요일",
            }
        )

    async def images(*args, **kwargs):
        return response_with(
            {"originimgurl": "https://example.com/detail.jpg"}
        )

    monkeypatch.setattr(adapter_module, "get_place_common_info", common)
    monkeypatch.setattr(adapter_module, "get_place_intro_info", intro)
    monkeypatch.setattr(adapter_module, "get_place_images", images)

    adapter = TourApiAdapter(cache_ttl_seconds=60)
    first = await adapter.get_place_detail("123")
    second = await adapter.get_place_detail("123")

    assert first.overview == "상세 소개"
    assert first.open_time == "10:00"
    assert first.close_time == "22:00"
    assert first.closed_days_text == "매주 월요일"
    assert first.thumbnail_url == "https://example.com/detail.jpg"
    assert second == first
    assert calls["common"] == 1
    assert calls["intro_content_type_id"] == "39"


@pytest.mark.anyio
async def test_detail_keeps_unknown_hours_and_image_as_none(monkeypatch) -> None:
    async def common(*args, **kwargs):
        return response_with(
            {
                "contentid": "123",
                "contenttypeid": "12",
                "title": "정보 없는 장소",
                "mapx": "127.0",
                "mapy": "37.5",
                "addr1": "서울특별시",
            }
        )

    async def empty(*args, **kwargs):
        return response_with([])

    monkeypatch.setattr(adapter_module, "get_place_common_info", common)
    monkeypatch.setattr(adapter_module, "get_place_intro_info", empty)
    monkeypatch.setattr(adapter_module, "get_place_images", empty)

    place = await TourApiAdapter().get_place_detail("123")

    assert place.open_time is None
    assert place.close_time is None
    assert place.thumbnail_url is None


@pytest.mark.anyio
async def test_nearby_page_uses_category_pagination_and_cache(
    monkeypatch,
) -> None:
    from app.models.place import PlaceCategory

    calls = []

    async def nearby(**kwargs):
        calls.append(kwargs)

        return {
            "response": {
                "body": {
                    "pageNo": 2,
                    "numOfRows": 20,
                    "totalCount": 45,
                    "items": {
                        "item": [
                            {
                                "contentid": "123",
                                "contenttypeid": "39",
                                "title": "테스트 식당",
                                "mapx": "127.0",
                                "mapy": "37.5",
                                "addr1": "서울특별시",
                            }
                        ]
                    },
                }
            }
        }

    monkeypatch.setattr(
        adapter_module,
        "get_nearby_places",
        nearby,
    )

    adapter = TourApiAdapter(cache_ttl_seconds=60)

    first = await adapter.get_nearby_place_page(
        longitude=127.0,
        latitude=37.5,
        radius=2000,
        page_no=2,
        num_of_rows=20,
        category=PlaceCategory.RESTAURANT,
    )

    second = await adapter.get_nearby_place_page(
        longitude=127.0,
        latitude=37.5,
        radius=2000,
        page_no=2,
        num_of_rows=20,
        category=PlaceCategory.RESTAURANT,
    )

    assert len(first.places) == 1
    assert first.next_page_token == "3"
    assert second == first

    assert len(calls) == 1
    assert calls[0]["page_no"] == 2
    assert calls[0]["num_of_rows"] == 20
    assert calls[0]["content_type_id"] == "39"

import json
from pathlib import Path
import pytest
from pydantic import ValidationError

from app.external.tour_api.mapper import (
    tour_api_item_to_place,
    tour_api_items_to_places,
)
from app.external.tour_api.client import extract_items
from app.external.tour_api.mapper import tour_api_item_to_place
from app.models.place import Place, PlaceCategory, PlaceSource


SAMPLE_PATH = (
    Path(__file__).resolve().parents[1]
    / "samples"
    / "tour_api"
    / "location_based_list.json"
)


def test_location_sample_maps_to_internal_place() -> None:
    data = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    [item] = extract_items(data)

    place = tour_api_item_to_place(item)

    assert place.place_id == "tour_123456"
    assert place.category == PlaceCategory.RESTAURANT
    assert place.latitude == 37.5122
    assert place.longitude == 127.0719
    assert place.address == "서울특별시 송파구 올림픽로 25"
    assert place.distance_meters == 350.5
    assert place.model_dump()["placeId"] == "tour_123456"
    assert place.model_dump()["defaultStayMinutes"] == 60


def test_extract_items_accepts_empty_and_single_item_responses() -> None:
    assert extract_items({"response": {"body": {"items": ""}}}) == []
    single = {"contentid": "1"}
    data = {"response": {"body": {"items": {"item": single}}}}
    assert extract_items(data) == [single]

def make_valid_item() -> dict[str, str]:
    return {
        "contentid": "123456",
        "contenttypeid": "39",
        "title": "테스트 음식점",
        "mapx": "127.0719",
        "mapy": "37.5122",
        "addr1": "서울특별시",
        "addr2": "송파구",
    }

@pytest.mark.parametrize(
    "missing_field",
    [
        "contentid",
        "title",
        "mapx",
        "mapy",
    ],
)
def test_invalid_required_field_is_rejected(
    missing_field: str,
) -> None:
    item = make_valid_item()
    item.pop(missing_field)

    with pytest.raises(ValueError):
        tour_api_item_to_place(item)

@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("mapx", "not-a-number"),
        ("mapy", "not-a-number"),
        ("mapx", "181"),
        ("mapy", "91"),
    ],
)
def test_invalid_coordinate_is_rejected(
    field: str,
    value: str,
) -> None:
    item = make_valid_item()
    item[field] = value

    with pytest.raises(ValueError):
        tour_api_item_to_place(item)

def test_invalid_item_is_skipped_from_list() -> None:
    valid_item = make_valid_item()

    invalid_item = make_valid_item()
    invalid_item["contentid"] = "invalid"
    invalid_item["mapx"] = "not-a-number"

    places = tour_api_items_to_places(
        [
            valid_item,
            invalid_item,
        ]
    )

    assert len(places) == 1
    assert places[0].place_id == "tour_123456"


def test_activity_content_type_maps_to_activity() -> None:
    item = make_valid_item()
    item["contenttypeid"] = "28"

    place = tour_api_item_to_place(item)

    assert place.category == PlaceCategory.ACTIVITY


def test_external_source_requires_source_content_id() -> None:
    with pytest.raises(ValidationError):
        Place(
            placeId="kakao_unknown",
            name="테스트 장소",
            category=PlaceCategory.OTHER,
            latitude=37.5,
            longitude=127.0,
            address="서울특별시",
            source=PlaceSource.KAKAO,
        )


def test_user_pick_allows_missing_source_content_id() -> None:
    place = Place(
        placeId="user_pick_001",
        name="지도에서 선택한 위치",
        category=PlaceCategory.OTHER,
        latitude=37.5,
        longitude=127.0,
        address="서울특별시",
        source=PlaceSource.USER_PICK,
    )

    assert place.source_content_id is None

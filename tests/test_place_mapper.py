import json
from pathlib import Path

from app.external.tour_api.client import extract_items
from app.external.tour_api.mapper import tour_api_item_to_place
from app.models.place import PlaceCategory


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

import json
from itertools import permutations
from pathlib import Path

from app.algorithms.itinerary_generator import generate_itinerary
from app.algorithms.travel_time import TravelTimeMatrix
from app.models.itinerary import (
    ItineraryItemType,
    TripInput,
    normalize_short_description,
)
from app.models.place import Place


SAMPLE_ROOT = Path(__file__).resolve().parents[1] / "samples" / "algorithm"


def test_generates_anchor_based_itinerary_with_fake_matrix() -> None:
    trip = TripInput.model_validate_json(
        (SAMPLE_ROOT / "trip_input.json").read_text(encoding="utf-8")
    )
    places = [
        Place.model_validate(value)
        for value in json.loads(
            (SAMPLE_ROOT / "places.json").read_text(encoding="utf-8")
        )
    ]
    places = [
        place.model_copy(
            update={
                "thumbnail_url": (
                    "https:"
                    + "//example.com/generated-place.jpg"
                ),
                "overview": (
                    "자동 생성 장소를\n  소개합니다."
                ),
            }
        )
        for place in places
    ]

    node_ids = [
        "arrival",
        "departure",
        "accommodation",
        "stadium",
        *(place.place_id for place in places),
    ]
    matrix = TravelTimeMatrix(
        minutes={pair: 15 for pair in permutations(node_ids, 2)}
    )

    result = generate_itinerary(trip, places, matrix)

    item_types = [
        item.item_type
        for day in result.days
        for item in day.items
    ]
    assert ItineraryItemType.ARRIVAL_POINT in item_types
    assert ItineraryItemType.ACCOMMODATION in item_types
    assert ItineraryItemType.STADIUM in item_types
    assert ItineraryItemType.DEPARTURE_POINT in item_types
    assert ItineraryItemType.PLACE in item_types

    generated_place = next(
        item
        for day in result.days
        for item in day.items
        if item.item_type == ItineraryItemType.PLACE
    )

    assert generated_place.thumbnail_url == (
        "https:"
        + "//example.com/generated-place.jpg"
    )
    assert generated_place.overview == (
        "자동 생성 장소를\n  소개합니다."
    )
    assert generated_place.short_description == (
        "자동 생성 장소를 소개합니다."
    )

    stadium = next(
        item
        for day in result.days
        for item in day.items
        if item.item_type == ItineraryItemType.STADIUM
    )
    assert stadium.place_id == "sajik"
    assert (
        trip.game_anchor.game_start_at - stadium.scheduled_start_at
    ).total_seconds() == 40 * 60

    departure = next(
        item
        for day in result.days
        for item in day.items
        if item.item_type == ItineraryItemType.DEPARTURE_POINT
    )
    assert (trip.trip_end_at - departure.scheduled_start_at).total_seconds() == 60 * 60
    assert result.total_travel_minutes == sum(
        item.travel_minutes_from_previous
        for day in result.days
        for item in day.items
    )
    travel_items = [
        item
        for day in result.days
        for item in day.items
        if item.travel_minutes_from_previous > 0
    ]
    assert travel_items
    assert all(item.travel_mode is not None for item in travel_items)
    assert all(
        item.travel_time_source is not None
        for item in travel_items
    )
    accommodation = next(
        item
        for day in result.days
        for item in day.items
        if item.item_type == ItineraryItemType.ACCOMMODATION
    )
    assert accommodation.place_id == trip.accommodation.place_id
    assert (
        accommodation.scheduled_end_at
        - accommodation.scheduled_start_at
    ).total_seconds() == 30 * 60
    assert all(
        item.transfer_buffer_minutes == 15
        for item in travel_items
    )


def test_required_missing_place_returns_conflict_metadata() -> None:
    trip = TripInput.model_validate_json(
        (SAMPLE_ROOT / "trip_input.json").read_text(encoding="utf-8")
    )
    matrix = TravelTimeMatrix(
        minutes={pair: 15 for pair in permutations(
            ["arrival", "departure", "accommodation", "stadium"], 2
        )}
    )

    result = generate_itinerary(trip, [], matrix)
    excluded = result.excluded_places[0]

    assert result.has_required_place_conflict is True
    assert excluded.is_required is True

def test_normalize_short_description_returns_none_for_missing_text() -> None:
    assert normalize_short_description(None) is None
    assert normalize_short_description("   \n  ") is None

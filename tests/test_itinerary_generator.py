import json
from itertools import permutations
from pathlib import Path

from app.algorithms.itinerary_generator import generate_itinerary
from app.algorithms.travel_time import TravelTimeMatrix
from app.models.itinerary import (
    ItineraryItemType,
    TravelTimeSource,
    TripInput,
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

    travelled_items = [
        item
        for day in result.days
        for item in day.items
        if item.travel_minutes_from_previous > 0
    ]

    assert travelled_items
    assert all(
        item.travel_time_source == TravelTimeSource.FAKE
        for item in travelled_items
    )

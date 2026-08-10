import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.algorithms.day_type import classify_day
from app.models.itinerary import (
    DayType,
    ItineraryItemType,
    ItineraryResult,
    TripInput,
)


SAMPLE_PATH = (
    Path(__file__).resolve().parents[1]
    / "samples"
    / "algorithm"
    / "trip_input.json"
)

RESULT_SAMPLE_PATH = (
    Path(__file__).resolve().parents[1]
    / "samples"
    / "algorithm"
    / "itinerary_result.json"
)


def test_trip_input_sample_is_valid() -> None:
    data = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    trip = TripInput.model_validate(data)

    assert trip.trip_id == "trip_001"
    assert trip.game_anchor.required_arrival_minutes == 40
    assert len(trip.selected_places) == 1
    assert trip.selected_places[0].place_id == "tour_123456"
    assert trip.selected_places[0].is_required is True


def test_itinerary_result_sample_is_valid() -> None:
    data = json.loads(
        RESULT_SAMPLE_PATH.read_text(encoding="utf-8")
    )

    result = ItineraryResult.model_validate(data)

    assert result.trip_id == "trip_001"
    assert result.days[0].items[0].item_type == (
        ItineraryItemType.ARRIVAL_POINT
    )
    assert result.days[0].items[1].item_type == (
        ItineraryItemType.PLACE
    )
    assert result.days[1].items[0].item_type == (
        ItineraryItemType.STADIUM
    )
    assert (
        result.model_dump()["days"][0]["items"][0]["type"]
        == "ARRIVAL_POINT"
    )
    assert (
        result.model_dump()["days"][0]["items"][0]["travelTimeSource"]
        is None
    )
    assert (
        result.model_dump()["days"][0]["items"][1]["travelTimeSource"]
        == "FAKE"
    )


def test_trip_input_rejects_naive_datetime() -> None:
    data = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    data["tripStartAt"] = "2026-08-14T10:30:00"

    with pytest.raises(ValidationError):
        TripInput.model_validate(data)


def test_classify_each_day_type() -> None:
    trip_start = date(2026, 8, 14)
    game_date = date(2026, 8, 15)
    trip_end = date(2026, 8, 17)

    assert classify_day(trip_start, trip_start, trip_end, game_date) == DayType.ARRIVAL_DAY
    assert classify_day(game_date, trip_start, trip_end, game_date) == DayType.GAME_DAY
    assert classify_day(date(2026, 8, 16), trip_start, trip_end, game_date) == DayType.NON_GAME_DAY
    assert classify_day(trip_end, trip_start, trip_end, game_date) == DayType.DEPARTURE_DAY


def test_itinerary_item_rejects_invalid_schedule() -> None:
    data = json.loads(
        RESULT_SAMPLE_PATH.read_text(encoding="utf-8")
    )["days"][0]["items"][0]
    data["scheduledEndAt"] = data["scheduledStartAt"]

    with pytest.raises(ValidationError):
        ItineraryResult.model_validate(
            {
                "tripId": "trip_001",
                "days": [
                    {
                        "date": "2026-08-14",
                        "dayType": "ARRIVAL_DAY",
                        "items": [data],
                    }
                ],
            }
        )


def test_itinerary_result_rejects_incorrect_travel_total() -> None:
    data = json.loads(
        RESULT_SAMPLE_PATH.read_text(encoding="utf-8")
    )
    data["totalTravelMinutes"] += 1

    with pytest.raises(ValidationError):
        ItineraryResult.model_validate(data)


def test_itinerary_result_rejects_unknown_exclusion_reason() -> None:
    data = json.loads(
        RESULT_SAMPLE_PATH.read_text(encoding="utf-8")
    )
    data["excludedPlaces"] = [
        {
            "placeId": "tour_999999",
            "reasonCode": "UNKNOWN_REASON",
            "message": "알 수 없는 제외 사유",
        }
    ]

    with pytest.raises(ValidationError):
        ItineraryResult.model_validate(data)

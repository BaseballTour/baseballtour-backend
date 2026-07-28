import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.algorithms.day_type import classify_day
from app.models.itinerary import DayType, TripInput


SAMPLE_PATH = (
    Path(__file__).resolve().parents[1]
    / "samples"
    / "algorithm"
    / "trip_input.json"
)


def test_trip_input_sample_is_valid() -> None:
    data = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    trip = TripInput.model_validate(data)

    assert trip.trip_id == "trip_001"
    assert trip.game_anchor.required_arrival_minutes == 40


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
    assert classify_day(date(2026, 8, 16), trip_start, trip_end, game_date) == DayType.FREE_DAY
    assert classify_day(trip_end, trip_start, trip_end, game_date) == DayType.DEPARTURE_DAY

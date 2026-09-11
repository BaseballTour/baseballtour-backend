from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.algorithms.itinerary_generator import generate_itinerary
from app.algorithms.itinerary_quality import evaluate_itinerary_quality
from app.algorithms.travel_time import TravelTimeMatrix
from app.models.itinerary import (
    GameAnchor,
    GeoPoint,
    ItineraryQualityCode,
    ItineraryQualityStatus,
    TripInput,
)


KST = ZoneInfo("Asia/Seoul")


def _trip() -> TripInput:
    return TripInput(
        trip_id="trip_quality",
        trip_start_at=datetime(2026, 9, 22, 12, tzinfo=KST),
        trip_end_at=datetime(2026, 9, 23, 22, tzinfo=KST),
        arrival_point=GeoPoint(
            name="서울역", address="서울역", latitude=37.5547, longitude=126.9706
        ),
        departure_point=GeoPoint(
            name="서울역", address="서울역", latitude=37.5547, longitude=126.9706
        ),
        game_anchor=GameAnchor(
            name="고척스카이돔",
            address="서울특별시 구로구 경인로 430",
            latitude=37.4982,
            longitude=126.8671,
            game_id="game_001",
            stadium_id="gocheok",
            game_start_at=datetime(2026, 9, 22, 18, 30, tzinfo=KST),
        ),
    )


def _matrix() -> TravelTimeMatrix:
    nodes = ("arrival", "departure", "stadium")
    matrix = TravelTimeMatrix(minutes={})
    for origin in nodes:
        for destination in nodes:
            matrix.minutes[(origin, destination)] = 0 if origin == destination else 30
    return matrix


def test_generated_anchor_only_itinerary_has_actionable_quality_warnings() -> None:
    trip = _trip()
    result = generate_itinerary(trip, [], _matrix())

    assert result.quality_summary is not None
    assert result.quality_summary.status == ItineraryQualityStatus.WARNING
    assert result.quality_summary.error_count == 0
    assert any(
        issue.code == ItineraryQualityCode.MEAL_MISSING
        for issue in result.quality_summary.issues
    )


def test_quality_gate_detects_stadium_time_contract_violation() -> None:
    trip = _trip()
    result = generate_itinerary(trip, [], _matrix())
    stadium = next(
        item
        for day in result.days
        for item in day.items
        if item.place_id == "gocheok"
    )
    stadium.scheduled_start_at += timedelta(minutes=10)
    stadium.scheduled_end_at += timedelta(minutes=10)

    quality = evaluate_itinerary_quality(trip, result)

    assert quality.status == ItineraryQualityStatus.FAIL
    assert any(
        issue.code == ItineraryQualityCode.STADIUM_ARRIVAL_TIME_INVALID
        for issue in quality.issues
    )

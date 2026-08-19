from datetime import datetime, timezone
from itertools import permutations
from pathlib import Path

from app.algorithms.itinerary_generator import generate_itinerary
from app.algorithms.travel_time import TravelTimeMatrix
from app.models.itinerary import (
    GameAnchor,
    GeoPoint,
    ItineraryItemAddedBy,
    SelectedPlaceInput,
    TripInput,
    ItineraryResult,
)
from app.models.place import Place, PlaceCategory, PlaceSource


UTC = timezone.utc
SAMPLE_ROOT = Path(__file__).resolve().parents[1] / "samples" / "algorithm"


def place(place_id: str, **updates) -> Place:
    values = {
        "place_id": place_id,
        "name": place_id,
        "category": PlaceCategory.TOURIST_SPOT,
        "latitude": 37.5,
        "longitude": 127.0,
        "source": PlaceSource.TOUR_API,
        "source_content_id": place_id,
        "default_stay_minutes": 60,
    }
    values.update(updates)
    return Place(**values)


def trip(selected: list[SelectedPlaceInput] | None = None) -> TripInput:
    return TripInput(
        trip_id="trip",
        trip_start_at=datetime(2026, 8, 14, 9, tzinfo=UTC),
        trip_end_at=datetime(2026, 8, 16, 20, tzinfo=UTC),
        arrival_point=GeoPoint(name="arrival", latitude=37.5, longitude=127),
        departure_point=GeoPoint(name="departure", latitude=37.5, longitude=127),
        game_anchor=GameAnchor(
            name="stadium",
            latitude=37.5,
            longitude=127,
            game_id="game",
            stadium_id="stadium",
            game_start_at=datetime(2026, 8, 15, 18, tzinfo=UTC),
        ),
        selected_places=selected or [],
    )


def matrix(*place_ids: str, default: int = 10) -> TravelTimeMatrix:
    ids = ["arrival", "departure", "stadium", *place_ids]
    return TravelTimeMatrix(
        minutes={pair: default for pair in permutations(ids, 2)}
    )


def test_fills_empty_itinerary_without_recommendation_count_limit() -> None:
    recommendations = [place(f"recommendation_{index}") for index in range(5)]
    result = generate_itinerary(
        trip(),
        [],
        matrix(*(item.place_id for item in recommendations)),
        recommended_places=recommendations,
    )

    recommended_items = [
        item
        for day in result.days
        for item in day.items
        if item.added_by == ItineraryItemAddedBy.ALGORITHM
    ]
    assert len(recommended_items) == 5
    assert result.auto_fill_applied is True
    assert result.auto_recommended_place_count == 5


def test_user_place_is_kept_and_marked_as_user() -> None:
    selected = place("selected", default_stay_minutes=600)
    recommendation = place("recommendation", default_stay_minutes=600)
    result = generate_itinerary(
        trip([SelectedPlaceInput(place_id=selected.place_id)]),
        [selected],
        matrix(selected.place_id, recommendation.place_id),
        recommended_places=[recommendation],
    )

    selected_item = next(
        item
        for day in result.days
        for item in day.items
        if item.place_id == selected.place_id
    )
    assert selected_item.added_by == ItineraryItemAddedBy.USER


def test_rejects_recommendation_with_more_than_thirty_minute_detour() -> None:
    recommendation = place("far")
    travel = matrix(recommendation.place_id, default=10)
    travel.minutes[("arrival", recommendation.place_id)] = 50
    travel.minutes[(recommendation.place_id, "departure")] = 50

    result = generate_itinerary(
        trip(), [], travel, recommended_places=[recommendation]
    )

    assert result.auto_fill_applied is False
    assert result.auto_recommended_place_count == 0


def test_does_not_auto_recommend_accommodation_or_unverified_festival() -> None:
    accommodation = place(
        "hotel", category=PlaceCategory.ACCOMMODATION
    )
    festival = place("festival", category=PlaceCategory.FESTIVAL)
    result = generate_itinerary(
        trip(),
        [],
        matrix(accommodation.place_id, festival.place_id),
        recommended_places=[accommodation, festival],
    )

    assert result.auto_recommended_place_count == 0


def test_auto_fill_can_be_disabled() -> None:
    recommendation = place("recommendation")
    result = generate_itinerary(
        trip().model_copy(update={"auto_fill_recommendations": False}),
        [],
        matrix(recommendation.place_id),
        recommended_places=[recommendation],
    )

    assert result.auto_fill_applied is False


def test_meeting_auto_fill_result_sample_is_valid() -> None:
    result = ItineraryResult.model_validate_json(
        (SAMPLE_ROOT / "auto_filled_itinerary.json").read_text(
            encoding="utf-8"
        )
    )

    assert result.algorithm_version == "auto-fill-v0.4"
    assert result.auto_fill_applied is True
    assert result.auto_recommended_place_count == 3
    assert sum(
        item.added_by == ItineraryItemAddedBy.ALGORITHM
        for day in result.days
        for item in day.items
    ) == 3

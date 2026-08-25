from datetime import datetime
from itertools import permutations
from pathlib import Path
from zoneinfo import ZoneInfo

from app.algorithms.itinerary_generator import (
    _has_consecutive_restaurants,
    generate_itinerary,
)
from app.algorithms.travel_time import TravelTimeMatrix
from app.models.itinerary import (
    GameAnchor,
    GeoPoint,
    ItineraryItemAddedBy,
    ItineraryItemType,
    SelectedPlaceInput,
    TripInput,
    ItineraryResult,
)
from app.models.place import (
    BusinessHoursRule,
    BusinessRuleStatus,
    Place,
    PlaceCategory,
    PlaceSource,
    Weekday,
)


UTC = ZoneInfo("Asia/Seoul")
SAMPLE_ROOT = Path(__file__).resolve().parents[1] / "samples" / "algorithm"


def test_consecutive_restaurants_are_detected() -> None:
    route = [
        place("restaurant-a", category=PlaceCategory.RESTAURANT),
        place("restaurant-b", category=PlaceCategory.RESTAURANT),
    ]
    assert _has_consecutive_restaurants(route) is True


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
    diagnostics = {}
    result = generate_itinerary(
        trip(),
        [],
        matrix(*(item.place_id for item in recommendations)),
        recommended_places=recommendations,
        recommendation_diagnostics=diagnostics,
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
    assert diagnostics["scheduledCount"] == 5
    assert "placementRejectedAttempts" in diagnostics


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


def test_place_item_preserves_restaurant_category() -> None:
    restaurant = place(
        "restaurant",
        category=PlaceCategory.RESTAURANT,
    )
    result = generate_itinerary(
        trip([SelectedPlaceInput(place_id=restaurant.place_id)]),
        [restaurant],
        matrix(restaurant.place_id),
    )

    item = next(
        item
        for day in result.days
        for item in day.items
        if item.place_id == restaurant.place_id
    )
    assert item.category == PlaceCategory.RESTAURANT
    assert item.model_dump()["category"] == "RESTAURANT"


def test_game_day_auto_fill_places_visit_before_stadium() -> None:
    game_day_cafe = place(
        "game_day_cafe",
        category=PlaceCategory.CAFE,
        business_hours_status=BusinessRuleStatus.PARSED,
        business_hours_rules=[
            BusinessHoursRule(
                weekdays=[Weekday.SATURDAY],
                open_time="09:00",
                close_time="17:00",
            )
        ],
    )
    result = generate_itinerary(
        trip(),
        [],
        matrix(game_day_cafe.place_id),
        recommended_places=[game_day_cafe],
    )

    game_day = next(day for day in result.days if day.day_type == "GAME_DAY")
    place_item = next(
        item for item in game_day.items if item.place_id == "game_day_cafe"
    )
    stadium_item = next(
        item
        for item in game_day.items
        if item.item_type == ItineraryItemType.STADIUM
    )
    assert place_item.scheduled_end_at < stadium_item.scheduled_start_at


def test_departure_day_auto_fill_starts_in_morning() -> None:
    departure_day_restaurant = place(
        "departure_day_restaurant",
        category=PlaceCategory.RESTAURANT,
        business_hours_status=BusinessRuleStatus.PARSED,
        business_hours_rules=[
            BusinessHoursRule(
                weekdays=[Weekday.SUNDAY],
                open_time="09:00",
                close_time="20:00",
            )
        ],
    )
    result = generate_itinerary(
        trip(),
        [],
        matrix(departure_day_restaurant.place_id),
        recommended_places=[departure_day_restaurant],
    )

    departure_day = next(
        day for day in result.days if day.day_type == "DEPARTURE_DAY"
    )
    place_item = next(
        item
        for item in departure_day.items
        if item.place_id == "departure_day_restaurant"
    )
    departure_item = next(
        item
        for item in departure_day.items
        if item.item_type == ItineraryItemType.DEPARTURE_POINT
    )
    assert place_item.scheduled_start_at.hour < 12
    assert place_item.scheduled_end_at < departure_item.scheduled_start_at


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

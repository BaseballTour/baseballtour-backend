from datetime import datetime
from itertools import permutations
from zoneinfo import ZoneInfo

from app.algorithms.itinerary_generator import generate_itinerary
from app.algorithms.travel_time import TravelTimeMatrix
from app.models.itinerary import (
    ExcludedReasonCode,
    GameAnchor,
    GeoPoint,
    SelectedPlaceInput,
    TripInput,
)
from app.models.place import Place, PlaceSource


UTC = ZoneInfo("Asia/Seoul")


def make_place(place_id: str, **updates) -> Place:
    values = {
        "place_id": place_id,
        "name": place_id,
        "latitude": 37.5,
        "longitude": 127.0,
        "source": PlaceSource.TOUR_API,
        "source_content_id": place_id,
        "default_stay_minutes": 60,
    }
    values.update(updates)
    return Place(**values)


def make_trip(
    selections: list[SelectedPlaceInput],
    *,
    start: datetime = datetime(2026, 8, 14, 10, tzinfo=UTC),
    end: datetime = datetime(2026, 8, 16, 20, tzinfo=UTC),
) -> TripInput:
    return TripInput(
        trip_id="trip",
        trip_start_at=start,
        trip_end_at=end,
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
        selected_places=selections,
    )


def matrix_for(*place_ids: str, default: int = 10) -> TravelTimeMatrix:
    ids = ["arrival", "departure", "stadium", *place_ids]
    return TravelTimeMatrix(
        minutes={pair: default for pair in permutations(ids, 2)}
    )


def test_place_closed_on_earlier_days_is_assigned_to_open_day() -> None:
    place = make_place(
        "sunday_only",
        business_hours_status="PARSED",
        business_hours_rules=[
            {
                "weekdays": ["SUNDAY"],
                "openTime": "09:00",
                "closeTime": "18:00",
            }
        ],
    )
    trip = make_trip([SelectedPlaceInput(place_id=place.place_id)])

    result = generate_itinerary(
        trip, [place], matrix_for(place.place_id)
    )

    scheduled_day = next(
        day.date
        for day in result.days
        if any(item.place_id == place.place_id for item in day.items)
    )
    assert scheduled_day.isoformat() == "2026-08-16"


def test_required_place_is_selected_before_optional_when_only_one_fits() -> None:
    required = make_place("required", default_stay_minutes=400)
    optional = make_place("optional", default_stay_minutes=400)
    trip = make_trip(
        [
            SelectedPlaceInput(place_id=optional.place_id),
            SelectedPlaceInput(place_id=required.place_id, is_required=True),
        ],
        start=datetime(2026, 8, 15, 9, tzinfo=UTC),
        end=datetime(2026, 8, 15, 22, tzinfo=UTC),
    )

    result = generate_itinerary(
        trip,
        [optional, required],
        matrix_for(optional.place_id, required.place_id),
    )

    scheduled_ids = {
        item.place_id for day in result.days for item in day.items
    }
    assert required.place_id in scheduled_ids
    assert optional.place_id not in scheduled_ids


def test_admission_deadline_has_specific_exclusion_reason() -> None:
    place = make_place(
        "closed_entry",
        admission_deadline_status="PARSED",
        admission_deadline_time="08:00",
        admission_deadline_text="입장 마감 08:00",
    )
    trip = make_trip(
        [SelectedPlaceInput(place_id=place.place_id, is_required=True)],
        start=datetime(2026, 8, 15, 9, tzinfo=UTC),
        end=datetime(2026, 8, 15, 22, tzinfo=UTC),
    )

    result = generate_itinerary(
        trip, [place], matrix_for(place.place_id)
    )

    assert result.excluded_places[0].reason_code == (
        ExcludedReasonCode.ADMISSION_DEADLINE
    )
    assert result.has_required_place_conflict is True


def test_game_arrival_failure_has_anchor_conflict_reason() -> None:
    place = make_place("too_far")
    trip = make_trip(
        [SelectedPlaceInput(place_id=place.place_id)],
        start=datetime(2026, 8, 15, 9, tzinfo=UTC),
        end=datetime(2026, 8, 15, 22, tzinfo=UTC),
    )

    result = generate_itinerary(
        trip, [place], matrix_for(place.place_id, default=250)
    )

    assert result.excluded_places[0].reason_code == (
        ExcludedReasonCode.ANCHOR_CONFLICT
    )


def test_same_input_has_deterministic_result() -> None:
    places = [make_place("b"), make_place("a")]
    trip = make_trip(
        [SelectedPlaceInput(place_id=place.place_id) for place in places]
    )
    matrix = matrix_for("a", "b")

    first = generate_itinerary(trip, places, matrix)
    second = generate_itinerary(trip, list(reversed(places)), matrix)

    assert first.model_dump() == second.model_dump()

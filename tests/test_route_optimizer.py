from datetime import date, datetime, timezone

from app.algorithms.itinerary_generator import _date_affinity_penalty, _exclusion_reason, _hours_for_date, _is_closed, _parse_time
from app.algorithms.route_optimizer import greedy_insertion, improve_route_2opt, route_travel_minutes
from app.algorithms.travel_time import TravelTimeMatrix
from app.models.itinerary import ExcludedReasonCode, GameAnchor, GeoPoint, SelectedPlaceInput, TripInput
from app.models.place import Place, PlaceSource


UTC = timezone.utc


def make_place(place_id: str) -> Place:
    return Place(
        place_id=place_id, name=place_id, latitude=37.5, longitude=127.0,
        source=PlaceSource.TOUR_API, source_content_id=place_id,
        default_stay_minutes=30,
    )


def complete_matrix(ids: list[str], default: int = 40) -> TravelTimeMatrix:
    return TravelTimeMatrix(minutes={(a, b): default for a in ids for b in ids if a != b})


def optimizer_args(matrix):
    return dict(
        target_date=date(2026, 8, 15), start_id="start", end_id="end",
        available_start=datetime(2026, 8, 15, 9, tzinfo=UTC),
        available_end=datetime(2026, 8, 15, 20, tzinfo=UTC),
        matrix=matrix, hours_for_date=_hours_for_date,
        is_closed=_is_closed, parse_time=_parse_time,
    )


def test_greedy_insertion_chooses_lowest_marginal_positions() -> None:
    a, b = make_place("a"), make_place("b")
    matrix = complete_matrix(["start", "end", "a", "b"])
    matrix.minutes.update({
        ("start", "a"): 5, ("a", "b"): 5, ("b", "end"): 5,
        ("start", "b"): 30, ("b", "a"): 30, ("a", "end"): 30,
        ("start", "end"): 40,
    })
    route, rejected = greedy_insertion(
        [b, a], is_required=lambda _: False,
        candidate_priority=lambda _: 0, **optimizer_args(matrix),
    )
    assert [place.place_id for place in route] == ["a", "b"]
    assert rejected == []


def test_two_opt_reduces_travel_without_breaking_constraints() -> None:
    places = [make_place(value) for value in "acbd"]
    ids = ["start", "end", *[place.place_id for place in places]]
    matrix = complete_matrix(ids)
    matrix.minutes.update({
        ("start", "a"): 5, ("a", "b"): 5, ("b", "c"): 5,
        ("c", "d"): 5, ("d", "end"): 5,
    })
    before = route_travel_minutes("start", places, "end", matrix)
    improved = improve_route_2opt(places, **optimizer_args(matrix))
    after = route_travel_minutes("start", improved, "end", matrix)
    assert after < before
    assert [place.place_id for place in improved] == list("abcd")


def test_date_affinity_prefers_stadium_near_place_on_game_day() -> None:
    place = make_place("near_stadium")
    trip = TripInput(
        trip_id="trip", trip_start_at=datetime(2026, 8, 14, 9, tzinfo=UTC),
        trip_end_at=datetime(2026, 8, 15, 22, tzinfo=UTC),
        arrival_point=GeoPoint(name="arrival", latitude=37.5, longitude=127),
        departure_point=GeoPoint(name="departure", latitude=37.5, longitude=127),
        accommodation=GeoPoint(name="hotel", latitude=37.5, longitude=127),
        game_anchor=GameAnchor(
            name="stadium", latitude=37.5, longitude=127,
            game_id="g", stadium_id="s",
            game_start_at=datetime(2026, 8, 15, 18, tzinfo=UTC),
        ),
        selected_places=[SelectedPlaceInput(place_id=place.place_id)],
    )
    matrix = complete_matrix(["arrival", "departure", "stadium", "accommodation", place.place_id])
    matrix.minutes.update({
        ("accommodation", place.place_id): 5,
        (place.place_id, "stadium"): 5,
        ("arrival", place.place_id): 30,
        (place.place_id, "accommodation"): 30,
    })
    game_penalty = _date_affinity_penalty(place, date(2026, 8, 15), trip, matrix)
    arrival_penalty = _date_affinity_penalty(place, date(2026, 8, 14), trip, matrix)
    assert game_penalty < arrival_penalty


def test_unlisted_weekend_is_closed_for_parsed_weekday_hours() -> None:
    from app.external.tour_api.business_hours import parse_business_hours
    status, text, rules = parse_business_hours("월~금 09:00~18:00")
    place = make_place("weekday_only").model_copy(update={
        "business_hours_status": status,
        "business_hours_text": text,
        "business_hours_rules": rules,
    })
    assert _is_closed(place, date(2026, 8, 15)) is True


def test_too_short_business_window_has_specific_exclusion_reason() -> None:
    from app.external.tour_api.business_hours import parse_business_hours
    status, text, rules = parse_business_hours("매일 10:00~10:20")
    place = make_place("short_window").model_copy(update={
        "business_hours_status": status,
        "business_hours_text": text,
        "business_hours_rules": rules,
    })
    assert _exclusion_reason(place, [date(2026, 8, 15)]) == ExcludedReasonCode.OUTSIDE_BUSINESS_HOURS

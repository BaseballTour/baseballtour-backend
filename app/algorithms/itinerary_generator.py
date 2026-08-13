from __future__ import annotations

from datetime import date, datetime, time, timedelta

from app.algorithms.day_type import classify_day
from app.algorithms.travel_time import TravelTimeMatrix
from app.algorithms.route_optimizer import (
    greedy_insertion,
    improve_route_2opt,
    simulate_route,
    transfer_buffer,
)
from app.models.itinerary import (
    DayType,
    ExcludedPlace,
    ExcludedReasonCode,
    ItineraryDay,
    ItineraryItem,
    ItineraryItemType,
    ItineraryResult,
    TravelMode,
    TravelTimeSource,
    TripInput,
)
from app.models.place import BusinessRuleStatus, Place, Weekday


DEFAULT_DAY_START = time(9, 0)
DEFAULT_DAY_END = time(21, 0)
DEFAULT_ANCHOR_MINUTES = 20
ACCOMMODATION_STAY_MINUTES = 30
DEFAULT_GAME_MINUTES = 180
DEPARTURE_BUFFER_MINUTES = 60


def generate_itinerary(
    trip: TripInput,
    places: list[Place],
    matrix: TravelTimeMatrix,
) -> ItineraryResult:
    """Anchor와 가까운 장소 우선 규칙을 적용하는 1차 일정 생성기."""
    selected = {item.place_id: item for item in trip.selected_places}
    candidates = list(
        {
            place.place_id: place
            for place in places
            if place.place_id in selected
        }.values()
    )
    excluded: list[ExcludedPlace] = []
    days: list[ItineraryDay] = []
    remaining = list(candidates)

    current_date = trip.trip_start_at.date()
    end_date = trip.trip_end_at.date()
    while current_date <= end_date:
        day_type = classify_day(
            current_date,
            trip.trip_start_at.date(),
            trip.trip_end_at.date(),
            trip.game_anchor.game_start_at.date(),
        )
        items, remaining = _schedule_day(
            current_date,
            day_type,
            trip,
            remaining,
            selected,
            matrix,
        )
        days.append(
            ItineraryDay(
                date=current_date,
                day_type=day_type,
                items=items,
            )
        )
        current_date += timedelta(days=1)

    trip_dates = [day.date for day in days]
    for place in remaining:
        reason_code = _exclusion_reason(place, trip_dates)
        messages = {
            ExcludedReasonCode.CLOSED_DAY: "여행 기간 동안 휴무입니다.",
            ExcludedReasonCode.OUTSIDE_BUSINESS_HOURS: "영업시간 안에 체류시간을 확보할 수 없습니다.",
            ExcludedReasonCode.INSUFFICIENT_TIME: "여행 시간 안에 방문 일정을 배정할 수 없습니다.",
        }
        excluded.append(
            ExcludedPlace(
                place_id=place.place_id,
                is_required=selected[place.place_id].is_required,
                selection_source=selected[place.place_id].selection_source,
                reason_code=reason_code,
                message=messages[reason_code],
            )
        )

    known_ids = {place.place_id for place in candidates}
    for selection in trip.selected_places:
        if selection.place_id not in known_ids:
            excluded.append(
                ExcludedPlace(
                    place_id=selection.place_id,
                    is_required=selection.is_required,
                    selection_source=selection.selection_source,
                    reason_code=ExcludedReasonCode.INVALID_PLACE,
                    message="장소 정보를 찾을 수 없습니다.",
                )
            )

    seen: set[str] = set()
    for selection in trip.selected_places:
        if selection.place_id in seen:
            excluded.append(
                ExcludedPlace(
                    place_id=selection.place_id,
                    is_required=selection.is_required,
                    selection_source=selection.selection_source,
                    reason_code=ExcludedReasonCode.DUPLICATE_PLACE,
                    message="같은 장소가 중복 선택되어 한 번만 배정했습니다.",
                )
            )
        seen.add(selection.place_id)

    total = sum(
        item.travel_minutes_from_previous
        for day in days
        for item in day.items
    )
    return ItineraryResult(
        trip_id=trip.trip_id,
        algorithm_version="greedy-insertion-2opt-v0.2",
        total_travel_minutes=total,
        days=days,
        excluded_places=excluded,
    )


def _schedule_day(
    target_date: date,
    day_type: DayType,
    trip: TripInput,
    candidates: list[Place],
    selections: dict,
    matrix: TravelTimeMatrix,
) -> tuple[list[ItineraryItem], list[Place]]:
    timezone = trip.trip_start_at.tzinfo
    assert timezone is not None
    day_start = datetime.combine(target_date, DEFAULT_DAY_START, timezone)
    day_end = datetime.combine(target_date, DEFAULT_DAY_END, timezone)
    items: list[ItineraryItem] = []
    previous_id = "accommodation" if trip.accommodation else "arrival"

    if day_type == DayType.ARRIVAL_DAY:
        day_start = trip.trip_start_at
        arrival_end = day_start + timedelta(minutes=DEFAULT_ANCHOR_MINUTES)
        items.append(
            _anchor_item(
                ItineraryItemType.ARRIVAL_POINT,
                trip.arrival_point,
                day_start,
                arrival_end,
            )
        )
        day_start = arrival_end
        previous_id = "arrival"

    if day_type == DayType.GAME_DAY:
        day_end = trip.game_anchor.game_start_at - timedelta(
            minutes=trip.game_anchor.required_arrival_minutes
        )

    if day_type == DayType.DEPARTURE_DAY:
        day_end = trip.trip_end_at - timedelta(
            minutes=DEPARTURE_BUFFER_MINUTES
        )

    final_anchor_id = None
    if day_type == DayType.GAME_DAY:
        final_anchor_id = "stadium"
    elif day_type == DayType.DEPARTURE_DAY:
        final_anchor_id = "departure"
    elif trip.accommodation is not None:
        final_anchor_id = "accommodation"

    optimizer_args = dict(
        target_date=target_date,
        start_id=previous_id,
        end_id=final_anchor_id,
        available_start=day_start,
        available_end=day_end,
        matrix=matrix,
        hours_for_date=_hours_for_date,
        is_closed=_is_closed,
        parse_time=_parse_time,
    )
    route, unscheduled = greedy_insertion(
        candidates,
        is_required=lambda place: selections[place.place_id].is_required,
        candidate_priority=lambda place: _date_affinity_penalty(
            place, target_date, trip, matrix
        ),
        **optimizer_args,
    )
    route = improve_route_2opt(route, **optimizer_args)
    visits = simulate_route(route, **optimizer_args) or []
    cursor = day_start
    for visit in visits:
        place = visit.place
        items.append(
            ItineraryItem(
                type=ItineraryItemType.PLACE,
                sequence=len(items) + 1,
                place_id=place.place_id,
                name=place.name,
                address=place.address or place.name,
                latitude=place.latitude,
                longitude=place.longitude,
                scheduled_start_at=visit.start,
                scheduled_end_at=visit.end,
                travel_minutes_from_previous=visit.travel_minutes,
                transfer_buffer_minutes=transfer_buffer(
                    previous_id, place.place_id
                ),
                travel_mode=matrix.get_mode(previous_id, place.place_id),
                travel_time_source=matrix.get_source(previous_id, place.place_id),
                is_required=selections[place.place_id].is_required,
                selection_source=selections[place.place_id].selection_source,
            )
        )
        cursor, previous_id = visit.end, place.place_id

    if day_type == DayType.GAME_DAY:
        travel = matrix.get(previous_id, "stadium")
        stadium_start = trip.game_anchor.game_start_at - timedelta(
            minutes=trip.game_anchor.required_arrival_minutes
        )
        items.append(
            _anchor_item(
                ItineraryItemType.STADIUM,
                trip.game_anchor,
                stadium_start,
                trip.game_anchor.game_start_at
                + timedelta(minutes=DEFAULT_GAME_MINUTES),
                sequence=len(items) + 1,
                place_id=trip.game_anchor.stadium_id,
                travel=travel,
                transfer_buffer=transfer_buffer(previous_id, "stadium"),
                travel_mode=matrix.get_mode(previous_id, "stadium"),
                travel_time_source=matrix.get_source(
                    previous_id,
                    "stadium",
                ),
            )
        )
        previous_id = "stadium"

    if trip.accommodation is not None and day_type != DayType.DEPARTURE_DAY:
        travel = matrix.get(previous_id, "accommodation")
        if day_type == DayType.GAME_DAY:
            previous_end = items[-1].scheduled_end_at
            start = previous_end + timedelta(
                minutes=travel + transfer_buffer(previous_id, "accommodation")
            )
        else:
            start = max(
                cursor + timedelta(
                    minutes=travel + transfer_buffer(previous_id, "accommodation")
                ),
                datetime.combine(
                    target_date,
                    DEFAULT_DAY_END,
                    timezone,
                ),
            )
        items.append(
            _anchor_item(
                ItineraryItemType.ACCOMMODATION,
                trip.accommodation,
                start,
                start + timedelta(minutes=ACCOMMODATION_STAY_MINUTES),
                sequence=len(items) + 1,
                travel=travel,
                transfer_buffer=transfer_buffer(previous_id, "accommodation"),
                travel_mode=matrix.get_mode(previous_id, "accommodation"),
                travel_time_source=matrix.get_source(
                    previous_id,
                    "accommodation",
                ),
            )
        )

    if day_type == DayType.DEPARTURE_DAY:
        travel = matrix.get(previous_id, "departure")
        start = trip.trip_end_at - timedelta(
            minutes=DEPARTURE_BUFFER_MINUTES
        )
        items.append(
            _anchor_item(
                ItineraryItemType.DEPARTURE_POINT,
                trip.departure_point,
                start,
                trip.trip_end_at,
                sequence=len(items) + 1,
                travel=travel,
                transfer_buffer=transfer_buffer(previous_id, "departure"),
                travel_mode=matrix.get_mode(previous_id, "departure"),
                travel_time_source=matrix.get_source(
                    previous_id,
                    "departure",
                ),
            )
        )

    for index, item in enumerate(items, start=1):
        item.sequence = index
    return items, unscheduled


def _anchor_item(
    item_type: ItineraryItemType,
    point,
    start: datetime,
    end: datetime,
    *,
    sequence: int = 1,
    place_id: str | None = None,
    travel: int = 0,
    transfer_buffer: int = 0,
    travel_mode: TravelMode | None = None,
    travel_time_source: TravelTimeSource | None = None,
) -> ItineraryItem:
    return ItineraryItem(
        type=item_type,
        sequence=sequence,
        place_id=place_id,
        name=point.name,
        address=getattr(point, "address", None) or point.name,
        latitude=point.latitude,
        longitude=point.longitude,
        scheduled_start_at=start,
        scheduled_end_at=end,
        travel_minutes_from_previous=travel,
        transfer_buffer_minutes=transfer_buffer,
        travel_mode=travel_mode,
        travel_time_source=travel_time_source,
        is_required=True,
    )


def _parse_time(value: str | None) -> time | None:
    if not value:
        return None
    for token in value.replace("~", " ").split():
        try:
            return time.fromisoformat(token[:5])
        except ValueError:
            continue
    return None


def _apply_open_time(start: datetime, value: str | None) -> datetime:
    opening = _parse_time(value)
    if opening is None:
        return start
    opening_at = datetime.combine(start.date(), opening, start.tzinfo)
    return max(start, opening_at)


def _fits_hours(end: datetime, value: str | None) -> bool:
    closing = _parse_time(value)
    if closing is None:
        return True
    return end <= datetime.combine(end.date(), closing, end.tzinfo)


def _is_closed(place: Place, target_date: date) -> bool:
    weekday = list(Weekday)[target_date.weekday()]
    if (
        place.closed_days_status == BusinessRuleStatus.PARSED
        and weekday in place.closed_weekdays
    ):
        return True
    if (
        place.business_hours_status == BusinessRuleStatus.PARSED
        and place.business_hours_rules
        and all(weekday not in rule.weekdays for rule in place.business_hours_rules)
    ):
        return True
    return False


def _hours_for_date(place: Place, target_date: date) -> tuple[str | None, str | None]:
    if place.business_hours_status != BusinessRuleStatus.PARSED:
        return None, None
    weekday = list(Weekday)[target_date.weekday()]
    for rule in place.business_hours_rules:
        if weekday in rule.weekdays:
            return rule.open_time, rule.close_time
    return None, None


def _day_anchor_ids(day_type: DayType, trip: TripInput) -> tuple[str, str | None]:
    start = "accommodation" if trip.accommodation else "arrival"
    if day_type == DayType.ARRIVAL_DAY:
        start = "arrival"
    if day_type == DayType.GAME_DAY:
        return start, "stadium"
    if day_type == DayType.DEPARTURE_DAY:
        return start, "departure"
    return start, "accommodation" if trip.accommodation else None


def _anchor_cost(place: Place, day_type: DayType, trip: TripInput, matrix: TravelTimeMatrix) -> int:
    start, end = _day_anchor_ids(day_type, trip)
    cost = matrix.get(start, place.place_id)
    if end is not None:
        cost += matrix.get(place.place_id, end)
    return cost


def _date_affinity_penalty(
    place: Place,
    target_date: date,
    trip: TripInput,
    matrix: TravelTimeMatrix,
) -> float:
    current_type = classify_day(
        target_date,
        trip.trip_start_at.date(),
        trip.trip_end_at.date(),
        trip.game_anchor.game_start_at.date(),
    )
    current_cost = _anchor_cost(place, current_type, trip, matrix)
    costs = []
    value = trip.trip_start_at.date()
    while value <= trip.trip_end_at.date():
        day_type = classify_day(
            value,
            trip.trip_start_at.date(),
            trip.trip_end_at.date(),
            trip.game_anchor.game_start_at.date(),
        )
        if not _is_closed(place, value):
            costs.append(_anchor_cost(place, day_type, trip, matrix))
        value += timedelta(days=1)
    return current_cost - min(costs) if costs else float("inf")


def _exclusion_reason(place: Place, trip_dates: list[date]) -> ExcludedReasonCode:
    if all(_is_closed(place, value) for value in trip_dates):
        return ExcludedReasonCode.CLOSED_DAY
    if place.business_hours_status == BusinessRuleStatus.PARSED:
        for value in trip_dates:
            if _is_closed(place, value):
                continue
            opening, closing = _hours_for_date(place, value)
            open_value, close_value = _parse_time(opening), _parse_time(closing)
            if open_value is None or close_value is None:
                continue
            available_minutes = (
                datetime.combine(value, close_value)
                - datetime.combine(value, open_value)
            ).total_seconds() / 60
            if available_minutes >= place.default_stay_minutes:
                return ExcludedReasonCode.INSUFFICIENT_TIME
        return ExcludedReasonCode.OUTSIDE_BUSINESS_HOURS
    return ExcludedReasonCode.INSUFFICIENT_TIME

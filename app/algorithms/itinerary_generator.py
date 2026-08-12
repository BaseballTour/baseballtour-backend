from __future__ import annotations

from datetime import date, datetime, time, timedelta

from app.algorithms.day_type import classify_day
from app.algorithms.travel_time import TravelTimeMatrix
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
        reason_code = (
            ExcludedReasonCode.CLOSED_DAY
            if all(_is_closed(place, value) for value in trip_dates)
            else ExcludedReasonCode.INSUFFICIENT_TIME
        )
        excluded.append(
            ExcludedPlace(
                place_id=place.place_id,
                reason_code=reason_code,
                message=(
                    "여행 기간 동안 휴무입니다."
                    if reason_code == ExcludedReasonCode.CLOSED_DAY
                    else "여행 시간 안에 방문 일정을 배정할 수 없습니다."
                ),
            )
        )

    known_ids = {place.place_id for place in candidates}
    for selection in trip.selected_places:
        if selection.place_id not in known_ids:
            excluded.append(
                ExcludedPlace(
                    place_id=selection.place_id,
                    reason_code=ExcludedReasonCode.INVALID_PLACE,
                    message="장소 정보를 찾을 수 없습니다.",
                )
            )

    total = sum(
        item.travel_minutes_from_previous
        for day in days
        for item in day.items
    )
    return ItineraryResult(
        trip_id=trip.trip_id,
        algorithm_version="greedy-anchor-v0.1",
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

    cursor = day_start
    unscheduled = list(candidates)
    while unscheduled:
        ordered = sorted(
            unscheduled,
            key=lambda place: (
                not selections[place.place_id].is_required,
                matrix.get(previous_id, place.place_id),
            ),
        )
        placed = False
        for place in ordered:
            if _is_closed(place, target_date):
                continue
            travel = matrix.get(previous_id, place.place_id)
            start = cursor + timedelta(minutes=travel)
            opening, closing = _hours_for_date(place, target_date)
            start = _apply_open_time(start, opening)
            end = start + timedelta(minutes=place.default_stay_minutes)
            tail_minutes = (
                matrix.get(place.place_id, final_anchor_id)
                if final_anchor_id is not None
                else 0
            )
            if (
                not _fits_hours(end, closing)
                or end + timedelta(minutes=tail_minutes) > day_end
            ):
                continue
            items.append(
                ItineraryItem(
                    type=ItineraryItemType.PLACE,
                    sequence=len(items) + 1,
                    place_id=place.place_id,
                    name=place.name,
                    address=place.address or place.name,
                    latitude=place.latitude,
                    longitude=place.longitude,
                    scheduled_start_at=start,
                    scheduled_end_at=end,
                    travel_minutes_from_previous=travel,
                    travel_mode=matrix.get_mode(
                        previous_id,
                        place.place_id,
                    ),
                    travel_time_source=matrix.get_source(
                        previous_id,
                        place.place_id,
                    ),
                    is_required=selections[place.place_id].is_required,
                )
            )
            cursor = end
            previous_id = place.place_id
            unscheduled.remove(place)
            placed = True
            break
        if not placed:
            break

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
            start = previous_end + timedelta(minutes=travel)
        else:
            start = max(
                cursor + timedelta(minutes=travel),
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
                start + timedelta(minutes=DEFAULT_ANCHOR_MINUTES),
                sequence=len(items) + 1,
                travel=travel,
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
    if place.closed_days_status != BusinessRuleStatus.PARSED:
        return False
    return list(Weekday)[target_date.weekday()] in place.closed_weekdays


def _hours_for_date(place: Place, target_date: date) -> tuple[str | None, str | None]:
    if place.business_hours_status != BusinessRuleStatus.PARSED:
        return None, None
    weekday = list(Weekday)[target_date.weekday()]
    for rule in place.business_hours_rules:
        if weekday in rule.weekdays:
            return rule.open_time, rule.close_time
    return None, None

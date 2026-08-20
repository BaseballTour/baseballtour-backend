from __future__ import annotations

from datetime import date, datetime, time, timedelta

from app.algorithms.day_type import classify_day
from app.algorithms.travel_time import TravelTimeMatrix
from app.algorithms.route_optimizer import (
    improve_route_2opt,
    route_travel_minutes,
    simulate_route,
    simulate_route_detailed,
    transfer_buffer,
)
from app.models.itinerary import (
    DayType,
    ExcludedPlace,
    ExcludedReasonCode,
    ItineraryDay,
    ItineraryItem,
    ItineraryItemAddedBy,
    ItineraryItemType,
    ItineraryResult,
    TravelMode,
    TravelTimeSource,
    TripInput,
)
from app.models.place import (
    BusinessRuleStatus,
    Place,
    PlaceCategory,
    Weekday,
)


DEFAULT_DAY_START = time(9, 0)
DEFAULT_DAY_END = time(21, 0)
DEFAULT_ANCHOR_MINUTES = 20
ACCOMMODATION_STAY_MINUTES = 30
DEFAULT_GAME_MINUTES = 180
DEPARTURE_BUFFER_MINUTES = 60
AUTO_FILL_MIN_REMAINING_MINUTES = 30
AUTO_FILL_MAX_DETOUR_MINUTES = 30


def generate_itinerary(
    trip: TripInput,
    places: list[Place],
    matrix: TravelTimeMatrix,
    *,
    recommended_places: list[Place] | None = None,
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
    routes, failed_reasons = _assign_places_to_dates(
        trip, candidates, selected, matrix
    )
    auto_ids: set[str] = set()
    if trip.auto_fill_recommendations and recommended_places:
        routes, auto_ids = _fill_routes_with_recommendations(
            trip,
            routes,
            recommended_places,
            matrix,
            excluded_ids=set(selected),
        )

    current_date = trip.trip_start_at.date()
    end_date = trip.trip_end_at.date()
    while current_date <= end_date:
        day_type = classify_day(
            current_date,
            trip.trip_start_at.date(),
            trip.trip_end_at.date(),
            trip.game_anchor.game_start_at.date(),
        )
        items = _schedule_day(
            current_date,
            day_type,
            trip,
            routes[current_date],
            selected,
            auto_ids,
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

    for place in candidates:
        if place.place_id not in failed_reasons:
            continue
        reason_code = failed_reasons[place.place_id]
        messages = {
            ExcludedReasonCode.CLOSED_DAY: "여행 기간 동안 휴무입니다.",
            ExcludedReasonCode.OUTSIDE_BUSINESS_HOURS: "영업시간 안에 체류시간을 확보할 수 없습니다.",
            ExcludedReasonCode.ADMISSION_DEADLINE: "입장 마감 전까지 방문할 수 없습니다.",
            ExcludedReasonCode.ANCHOR_CONFLICT: "방문하면 경기장 또는 출발지의 필수 도착시간을 지킬 수 없습니다.",
            ExcludedReasonCode.INSUFFICIENT_TIME: "여행 시간 안에 방문 일정을 배정할 수 없습니다.",
        }
        excluded.append(
            ExcludedPlace(
                place_id=place.place_id,
                is_required=selected[place.place_id].is_required,
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
        algorithm_version="auto-fill-v0.4",
        total_travel_minutes=total,
        days=days,
        excluded_places=excluded,
        auto_fill_applied=bool(auto_ids),
        auto_recommended_place_count=len(auto_ids),
    )


def _schedule_day(
    target_date: date,
    day_type: DayType,
    trip: TripInput,
    route: list[Place],
    selections: dict,
    auto_ids: set[str],
    matrix: TravelTimeMatrix,
) -> list[ItineraryItem]:
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
                category=place.category,
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
                is_required=(
                    selections[place.place_id].is_required
                    if place.place_id in selections
                    else False
                ),
                added_by=(
                    ItineraryItemAddedBy.ALGORITHM
                    if place.place_id in auto_ids
                    else ItineraryItemAddedBy.USER
                ),
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
                travel_time_source=matrix.get_source(previous_id, "stadium"),
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
                datetime.combine(target_date, DEFAULT_DAY_END, timezone),
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
                travel_time_source=matrix.get_source(previous_id, "accommodation"),
            )
        )

    if day_type == DayType.DEPARTURE_DAY:
        travel = matrix.get(previous_id, "departure")
        start = trip.trip_end_at - timedelta(minutes=DEPARTURE_BUFFER_MINUTES)
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
                travel_time_source=matrix.get_source(previous_id, "departure"),
            )
        )

    for index, item in enumerate(items, start=1):
        item.sequence = index
    return items


def _assign_places_to_dates(
    trip: TripInput,
    candidates: list[Place],
    selections: dict,
    matrix: TravelTimeMatrix,
) -> tuple[dict[date, list[Place]], dict[str, ExcludedReasonCode]]:
    """필수·일반·자동추천 순으로 모든 날짜와 삽입 위치를 비교한다."""
    dates: list[date] = []
    value = trip.trip_start_at.date()
    while value <= trip.trip_end_at.date():
        dates.append(value)
        value += timedelta(days=1)
    routes = {value: [] for value in dates}
    failures: dict[str, ExcludedReasonCode] = {}
    def order_key(place: Place) -> tuple:
        selection = selections[place.place_id]
        closing_values = []
        for target_date in dates:
            _, closing = _hours_for_date(place, target_date)
            parsed = _parse_time(closing)
            if parsed is not None:
                closing_values.append(parsed.hour * 60 + parsed.minute)
        earliest_close = min(closing_values) if closing_values else 24 * 60
        return (
            not selection.is_required,
            earliest_close,
            place.place_id,
        )

    for place in sorted(candidates, key=order_key):
        best: tuple[tuple, date, list[Place]] | None = None
        failure_codes: list[ExcludedReasonCode] = []
        for target_date in dates:
            day_type = classify_day(
                target_date,
                trip.trip_start_at.date(),
                trip.trip_end_at.date(),
                trip.game_anchor.game_start_at.date(),
            )
            args = _optimizer_args_for_date(
                target_date, day_type, trip, matrix
            )
            current = routes[target_date]
            current_cost = route_travel_minutes(
                args["start_id"], current, args["end_id"], matrix
            )
            for index in range(len(current) + 1):
                proposed = [*current[:index], place, *current[index:]]
                result = simulate_route_detailed(proposed, **args)
                if not result.feasible:
                    if result.failure is not None and (
                        result.failure.place_id in {None, place.place_id}
                    ):
                        failure_codes.append(result.failure.reason_code)
                    continue
                marginal = route_travel_minutes(
                    args["start_id"], proposed, args["end_id"], matrix
                ) - current_cost
                closing_slack = (
                    result.closing_slack_minutes
                    if result.closing_slack_minutes is not None
                    else 24 * 60
                )
                anchor_slack = result.anchor_slack_minutes or 0
                score = (
                    _date_affinity_penalty(
                        place, target_date, trip, matrix
                    ),
                    marginal,
                    closing_slack,
                    -anchor_slack,
                    target_date.toordinal(),
                    index,
                )
                if best is None or score < best[0]:
                    best = (score, target_date, proposed)

        if best is None:
            failures[place.place_id] = _representative_failure(
                failure_codes
            )
        else:
            routes[best[1]] = best[2]
    return routes, failures


def _fill_routes_with_recommendations(
    trip: TripInput,
    routes: dict[date, list[Place]],
    recommendations: list[Place],
    matrix: TravelTimeMatrix,
    *,
    excluded_ids: set[str],
) -> tuple[dict[date, list[Place]], set[str]]:
    """사용자 후보를 보존하면서 실행 가능한 추천 장소를 반복 삽입한다."""
    remaining = {
        place.place_id: place
        for place in recommendations
        if place.place_id not in excluded_ids
        and place.category != PlaceCategory.ACCOMMODATION
    }
    added: set[str] = set()

    while remaining:
        best: tuple[tuple, date, list[Place], Place] | None = None
        for target_date in sorted(routes):
            day_type = classify_day(
                target_date,
                trip.trip_start_at.date(),
                trip.trip_end_at.date(),
                trip.game_anchor.game_start_at.date(),
            )
            args = _optimizer_args_for_date(
                target_date, day_type, trip, matrix
            )
            current = routes[target_date]
            current_cost = route_travel_minutes(
                args["start_id"], current, args["end_id"], matrix
            )
            for place in sorted(
                remaining.values(), key=lambda item: item.place_id
            ):
                if (
                    place.category == PlaceCategory.FESTIVAL
                    and place.business_hours_status
                    != BusinessRuleStatus.PARSED
                ):
                    continue
                for index in range(len(current) + 1):
                    proposed = [*current[:index], place, *current[index:]]
                    result = simulate_route_detailed(proposed, **args)
                    if not result.feasible:
                        continue
                    if (
                        result.anchor_slack_minutes is None
                        or result.anchor_slack_minutes
                        < AUTO_FILL_MIN_REMAINING_MINUTES
                    ):
                        continue
                    marginal = route_travel_minutes(
                        args["start_id"], proposed, args["end_id"], matrix
                    ) - current_cost
                    if marginal > AUTO_FILL_MAX_DETOUR_MINUTES:
                        continue
                    visit = next(
                        item
                        for item in result.visits
                        if item.place.place_id == place.place_id
                    )
                    closing_slack = (
                        result.closing_slack_minutes
                        if result.closing_slack_minutes is not None
                        else 24 * 60
                    )
                    score = (
                        marginal,
                        -(result.anchor_slack_minutes or 0),
                        -closing_slack,
                        _meal_time_category_priority(
                            place.category, visit.start.time()
                        ),
                        abs(
                            result.anchor_slack_minutes
                            - AUTO_FILL_MIN_REMAINING_MINUTES
                        ),
                        target_date.toordinal(),
                        index,
                        place.place_id,
                    )
                    if best is None or score < best[0]:
                        best = (score, target_date, proposed, place)

        if best is None:
            break
        _, target_date, proposed, place = best
        routes[target_date] = proposed
        added.add(place.place_id)
        remaining.pop(place.place_id)

    return routes, added


def _meal_time_category_priority(
    category: PlaceCategory | str,
    visit_time: time,
) -> int:
    minute = visit_time.hour * 60 + visit_time.minute
    is_meal_time = 11 * 60 <= minute <= 14 * 60 or 17 * 60 <= minute <= 20 * 60
    if is_meal_time:
        return 0 if category == PlaceCategory.RESTAURANT else 1
    return (
        0
        if category
        in {
            PlaceCategory.TOURIST_SPOT,
            PlaceCategory.CAFE,
            PlaceCategory.CULTURAL_FACILITY,
        }
        else 1
    )


def _representative_failure(
    failures: list[ExcludedReasonCode],
) -> ExcludedReasonCode:
    if failures and all(
        reason == ExcludedReasonCode.CLOSED_DAY for reason in failures
    ):
        return ExcludedReasonCode.CLOSED_DAY
    precedence = (
        ExcludedReasonCode.ADMISSION_DEADLINE,
        ExcludedReasonCode.OUTSIDE_BUSINESS_HOURS,
        ExcludedReasonCode.ANCHOR_CONFLICT,
        ExcludedReasonCode.INSUFFICIENT_TIME,
    )
    return next(
        (reason for reason in precedence if reason in failures),
        ExcludedReasonCode.INSUFFICIENT_TIME,
    )


def _optimizer_args_for_date(
    target_date: date,
    day_type: DayType,
    trip: TripInput,
    matrix: TravelTimeMatrix,
) -> dict:
    timezone = trip.trip_start_at.tzinfo
    assert timezone is not None
    start_id = "accommodation" if trip.accommodation else "arrival"
    available_start = datetime.combine(
        target_date, DEFAULT_DAY_START, timezone
    )
    available_end = datetime.combine(
        target_date, DEFAULT_DAY_END, timezone
    )
    end_id = "accommodation" if trip.accommodation else None
    if day_type == DayType.ARRIVAL_DAY:
        start_id = "arrival"
        available_start = trip.trip_start_at + timedelta(
            minutes=DEFAULT_ANCHOR_MINUTES
        )
    if day_type == DayType.GAME_DAY:
        end_id = "stadium"
        available_end = trip.game_anchor.game_start_at - timedelta(
            minutes=trip.game_anchor.required_arrival_minutes
        )
    elif day_type == DayType.DEPARTURE_DAY:
        end_id = "departure"
        available_end = trip.trip_end_at - timedelta(
            minutes=DEPARTURE_BUFFER_MINUTES
        )
    return {
        "target_date": target_date,
        "start_id": start_id,
        "end_id": end_id,
        "available_start": available_start,
        "available_end": available_end,
        "matrix": matrix,
        "hours_for_date": _hours_for_date,
        "is_closed": _is_closed,
        "parse_time": _parse_time,
    }


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

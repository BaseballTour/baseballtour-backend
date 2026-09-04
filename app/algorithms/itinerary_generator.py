from __future__ import annotations

from datetime import date, datetime, time, timedelta
import logging
from collections import Counter

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
    normalize_short_description,
    ItineraryResult,
    TravelMode,
    TravelTimeSource,
    TripInput,
)
from app.models.place import (
    BusinessHoursRule,
    BusinessRuleStatus,
    Place,
    PlaceCategory,
    Weekday,
)
from app.models.travel_preferences import ScheduleDensity, TravelStyle


logger = logging.getLogger(__name__)


DEFAULT_DAY_START = time(9, 0)
DEFAULT_DAY_END = time(21, 0)
DEFAULT_ANCHOR_MINUTES = 20
ACCOMMODATION_STAY_MINUTES = 30
DEFAULT_GAME_MINUTES = 180
DEPARTURE_BUFFER_MINUTES = 60


AUTO_FILL_DENSITY_POLICIES = {
    ScheduleDensity.LIGHT: (0.35, 45),
    ScheduleDensity.MODERATE: (0.50, 30),
    ScheduleDensity.DENSE: (0.60, 15),
}
AUTO_FILL_STYLE_POLICIES = {
    TravelStyle.RELAXED: (0.35, 45),
    TravelStyle.BALANCED: (0.50, 30),
    TravelStyle.EXPLORER: (0.60, 15),
}


def generate_itinerary(
    trip: TripInput,
    places: list[Place],
    matrix: TravelTimeMatrix,
    *,
    recommended_places: list[Place] | None = None,
    supplemental_recommendations_by_date: dict[date, list[Place]] | None = None,
    recommendation_diagnostics: dict[str, object] | None = None,
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
            diagnostics=recommendation_diagnostics,
        )
    if trip.auto_fill_recommendations and supplemental_recommendations_by_date:
        for target_date in sorted(supplemental_recommendations_by_date):
            if target_date not in routes:
                continue
            supplemental = supplemental_recommendations_by_date[target_date]
            if not supplemental:
                continue
            occupied_ids = {
                place.place_id
                for route in routes.values()
                for place in route
            }
            supplemental_diagnostics: dict[str, object] = {}
            updated, supplemental_ids = _fill_routes_with_recommendations(
                trip,
                {target_date: routes[target_date]},
                supplemental,
                matrix,
                excluded_ids=set(selected) | auto_ids | occupied_ids,
                diagnostics=supplemental_diagnostics,
            )
            routes[target_date] = updated[target_date]
            auto_ids.update(supplemental_ids)
            _merge_supplemental_diagnostics(
                recommendation_diagnostics,
                supplemental_diagnostics,
                target_date,
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
    total_distance = sum(
        item.travel_distance_meters_from_previous
        for day in days
        for item in day.items
    )
    return ItineraryResult(
        trip_id=trip.trip_id,
        algorithm_version="auto-fill-v0.6",
        total_travel_minutes=total,
        total_travel_distance_meters=total_distance,
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
    is_arrival_date = target_date == trip.trip_start_at.date()
    is_departure_date = target_date == trip.trip_end_at.date()
    is_game_date = target_date == trip.game_anchor.game_start_at.date()

    if is_arrival_date:
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

    if is_game_date:
        day_end = trip.game_anchor.game_start_at - timedelta(
            minutes=trip.game_anchor.required_arrival_minutes
        )

    if is_departure_date:
        day_end = trip.trip_end_at - timedelta(
            minutes=DEPARTURE_BUFFER_MINUTES
        )

    final_anchor_id = None
    if is_game_date:
        final_anchor_id = "stadium"
    elif is_departure_date:
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
                thumbnail_url=place.thumbnail_url,
                short_description=normalize_short_description(
                    place.overview
                ),
                overview=place.overview,
                name=place.name,
                address=place.address or place.name,
                latitude=place.latitude,
                longitude=place.longitude,
                scheduled_start_at=visit.start,
                scheduled_end_at=visit.end,
                travel_minutes_from_previous=visit.travel_minutes,
                travel_distance_meters_from_previous=(
                    matrix.get_distance_meters(previous_id, place.place_id)
                ),
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

    if is_game_date:
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
                travel_distance=matrix.get_distance_meters(
                    previous_id, "stadium"
                ),
                transfer_buffer=transfer_buffer(previous_id, "stadium"),
                travel_mode=matrix.get_mode(previous_id, "stadium"),
                travel_time_source=matrix.get_source(previous_id, "stadium"),
            )
        )
        previous_id = "stadium"

    if trip.accommodation is not None and not is_departure_date:
        travel = matrix.get(previous_id, "accommodation")
        if is_game_date:
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
                place_id=trip.accommodation.place_id,
                travel=travel,
                travel_distance=matrix.get_distance_meters(
                    previous_id, "accommodation"
                ),
                transfer_buffer=transfer_buffer(previous_id, "accommodation"),
                travel_mode=matrix.get_mode(previous_id, "accommodation"),
                travel_time_source=matrix.get_source(previous_id, "accommodation"),
            )
        )

    if is_departure_date:
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
                travel_distance=matrix.get_distance_meters(
                    previous_id, "departure"
                ),
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


def _merge_supplemental_diagnostics(
    diagnostics: dict[str, object] | None,
    supplemental: dict[str, object],
    target_date: date,
) -> None:
    if diagnostics is None:
        return

    supplemental_count = int(supplemental.get("scheduledCount", 0))
    diagnostics["scheduledCount"] = (
        int(diagnostics.get("scheduledCount", 0)) + supplemental_count
    )
    scheduled_by_day = dict(diagnostics.get("scheduledByDay", {}))
    target_key = target_date.isoformat()
    supplemental_by_day = dict(supplemental.get("scheduledByDay", {}))
    scheduled_by_day[target_key] = int(
        scheduled_by_day.get(target_key, 0)
    ) + int(supplemental_by_day.get(target_key, 0))
    diagnostics["scheduledByDay"] = scheduled_by_day

    rejected = Counter(diagnostics.get("placementRejectedAttempts", {}))
    rejected.update(supplemental.get("placementRejectedAttempts", {}))
    diagnostics["placementRejectedAttempts"] = dict(sorted(rejected.items()))

    rejected_by_day = dict(
        diagnostics.get("placementRejectedAttemptsByDay", {})
    )
    target_rejected = Counter(rejected_by_day.get(target_key, {}))
    supplemental_rejected_by_day = dict(
        supplemental.get("placementRejectedAttemptsByDay", {})
    )
    target_rejected.update(supplemental_rejected_by_day.get(target_key, {}))
    rejected_by_day[target_key] = dict(sorted(target_rejected.items()))
    diagnostics["placementRejectedAttemptsByDay"] = rejected_by_day


def _route_uses_estimated_time(
    start_id: str,
    route: list[Place],
    end_id: str | None,
    matrix: TravelTimeMatrix,
) -> bool:
    previous = start_id
    for place in route:
        if (
            matrix.get_source(previous, place.place_id)
            == TravelTimeSource.ESTIMATED
        ):
            return True
        previous = place.place_id
    return (
        end_id is not None
        and matrix.get_source(previous, end_id)
        == TravelTimeSource.ESTIMATED
    )


def _fill_routes_with_recommendations(
    trip: TripInput,
    routes: dict[date, list[Place]],
    recommendations: list[Place],
    matrix: TravelTimeMatrix,
    *,
    excluded_ids: set[str],
    diagnostics: dict[str, object] | None = None,
) -> tuple[dict[date, list[Place]], set[str]]:
    """사용자 후보를 보존하면서 실행 가능한 추천 장소를 반복 삽입한다."""
    remaining = {
        place.place_id: place
        for place in recommendations
        if place.place_id not in excluded_ids
        and place.category != PlaceCategory.ACCOMMODATION
        and place.category != PlaceCategory.OTHER
    }
    added: set[str] = set()
    rejected: Counter[str] = Counter()
    rejected_by_day: dict[date, Counter[str]] = {
        target_date: Counter() for target_date in routes
    }
    scheduled_per_day: Counter[date] = Counter()
    density_efficiency, density_slack = (
        AUTO_FILL_DENSITY_POLICIES[trip.schedule_density]
    )
    style_efficiency, style_slack = AUTO_FILL_STYLE_POLICIES[
        trip.travel_style
    ]
    maximum_travel_ratio = min(density_efficiency, style_efficiency)
    minimum_non_game_slack = max(density_slack, style_slack)

    while remaining:
        best: tuple[tuple, date, list[Place], Place] | None = None
        for target_date in sorted(routes):
            day_type = classify_day(
                target_date,
                trip.trip_start_at.date(),
                trip.trip_end_at.date(),
                trip.game_anchor.game_start_at.date(),
            )
            day_fill_priority = _auto_fill_day_priority(day_type)
            args = _optimizer_args_for_date(
                target_date, day_type, trip, matrix
            )
            current = routes[target_date]
            current_result = simulate_route_detailed(current, **args)
            current_meals = (
                _covered_meal_periods(current_result.visits)
                if current_result.feasible
                else set()
            )
            current_cost = route_travel_minutes(
                args["start_id"], current, args["end_id"], matrix
            )
            minimum_anchor_slack = (
                0
                if day_type == DayType.GAME_DAY
                else minimum_non_game_slack
            )
            for place in sorted(
                remaining.values(), key=lambda item: item.place_id
            ):
                if (
                    place.category == PlaceCategory.FESTIVAL
                    and place.business_hours_status
                    != BusinessRuleStatus.PARSED
                ):
                    rejected["UNVERIFIED_FESTIVAL"] += 1
                    rejected_by_day[target_date][
                        "UNVERIFIED_FESTIVAL"
                    ] += 1
                    continue
                candidate = _place_for_next_meal_period(
                    place,
                    current_meals,
                    target_date=target_date,
                    available_start=args["available_start"],
                    available_end=args["available_end"],
                )
                if candidate is None:
                    rejected["NO_AVAILABLE_MEAL_PERIOD"] += 1
                    rejected_by_day[target_date][
                        "NO_AVAILABLE_MEAL_PERIOD"
                    ] += 1
                    continue
                for index in range(len(current) + 1):
                    proposed = [*current[:index], candidate, *current[index:]]
                    result = simulate_route_detailed(proposed, **args)
                    if not result.feasible:
                        reason = (
                            result.failure.reason_code.value
                            if result.failure is not None
                            else "INFEASIBLE"
                        )
                        rejected[reason] += 1
                        rejected_by_day[target_date][reason] += 1
                        continue
                    if (
                        result.anchor_slack_minutes is None
                        or result.anchor_slack_minutes
                        < minimum_anchor_slack
                    ):
                        rejected["INSUFFICIENT_TIME"] += 1
                        rejected_by_day[target_date]["INSUFFICIENT_TIME"] += 1
                        continue
                    marginal = route_travel_minutes(
                        args["start_id"], proposed, args["end_id"], matrix
                    ) - current_cost
                    route_travel = route_travel_minutes(
                        args["start_id"], proposed, args["end_id"], matrix
                    )
                    route_edges = len(proposed) + (
                        1 if args["end_id"] is not None else 0
                    )
                    route_travel += route_edges * 15
                    available_minutes = max(
                        1,
                        int(
                            (
                                args["available_end"]
                                - args["available_start"]
                            ).total_seconds()
                            // 60
                        ),
                    )
                    travel_ratio = route_travel / available_minutes
                    effective_ratio = maximum_travel_ratio
                    if _route_uses_estimated_time(
                        args["start_id"], proposed, args["end_id"], matrix
                    ):
                        effective_ratio = max(0.25, effective_ratio - 0.10)
                    if travel_ratio > effective_ratio:
                        rejected["ROUTE_INEFFICIENT"] += 1
                        rejected_by_day[target_date][
                            "ROUTE_INEFFICIENT"
                        ] += 1
                        continue
                    if _has_duplicate_meal_restaurants(result.visits):
                        rejected["CONSECUTIVE_RESTAURANT"] += 1
                        rejected_by_day[target_date][
                            "CONSECUTIVE_RESTAURANT"
                        ] += 1
                        continue
                    visit = next(
                        item
                        for item in result.visits
                        if item.place.place_id == place.place_id
                    )
                    if (
                        place.category == PlaceCategory.RESTAURANT
                        and _meal_period(visit.start.time()) is None
                    ):
                        rejected["OUTSIDE_MEAL_PERIOD"] += 1
                        rejected_by_day[target_date][
                            "OUTSIDE_MEAL_PERIOD"
                        ] += 1
                        continue
                    closing_slack = (
                        result.closing_slack_minutes
                        if result.closing_slack_minutes is not None
                        else 24 * 60
                    )
                    proposed_meals = _covered_meal_periods(
                        result.visits
                    )
                    meal_gain = len(proposed_meals - current_meals)
                    same_category_count = sum(
                        item.category == place.category for item in current
                    )
                    style_priority = (
                        same_category_count
                        if trip.travel_style == TravelStyle.EXPLORER
                        else (
                            marginal
                            if trip.travel_style == TravelStyle.RELAXED
                            else 0
                        )
                    )
                    score = (
                        scheduled_per_day[target_date],
                        day_fill_priority,
                        -meal_gain,
                        style_priority,
                        _meal_time_category_priority(
                            place, visit.start.time()
                        ),
                        marginal,
                        abs(
                            result.anchor_slack_minutes
                            - minimum_anchor_slack
                        ),
                        -closing_slack,
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
        scheduled_per_day[target_date] += 1
        remaining.pop(place.place_id)

    logger.info(
        "자동 추천 배치 진단: candidates=%s scheduled=%s rejected_attempts=%s",
        len(recommendations),
        len(added),
        dict(sorted(rejected.items())),
    )
    if diagnostics is not None:
        diagnostics["scheduledCount"] = len(added)
        diagnostics["scheduledByDay"] = {
            target_date.isoformat(): scheduled_per_day[target_date]
            for target_date in sorted(routes)
        }
        diagnostics["placementRejectedAttempts"] = dict(
            sorted(rejected.items())
        )
        diagnostics["placementRejectedAttemptsByDay"] = {
            target_date.isoformat(): dict(
                sorted(rejected_by_day[target_date].items())
            )
            for target_date in sorted(routes)
        }

    return routes, added


def _auto_fill_day_priority(day_type: DayType) -> int:
    """사용자에게 중요한 고정 Anchor 앞의 공백부터 자동 추천으로 채운다."""

    priorities = {
        DayType.GAME_DAY: 0,
        DayType.DEPARTURE_DAY: 1,
        DayType.NON_GAME_DAY: 2,
        DayType.ARRIVAL_DAY: 3,
    }
    return priorities[day_type]


def _has_consecutive_restaurants(route: list[Place]) -> bool:
    """자동 추천 결과에서 식당 두 곳이 연속되는 구성을 막습니다."""

    return any(
        previous.category == PlaceCategory.RESTAURANT
        and current.category == PlaceCategory.RESTAURANT
        for previous, current in zip(route, route[1:])
    )


def _has_duplicate_meal_restaurants(visits) -> bool:
    """같은 식사 시간대에 식당이 연달아 추천되는 경우만 차단한다."""

    for previous, current in zip(visits, visits[1:]):
        if (
            previous.place.category != PlaceCategory.RESTAURANT
            or current.place.category != PlaceCategory.RESTAURANT
        ):
            continue
        previous_period = _meal_period(previous.start.time())
        current_period = _meal_period(current.start.time())
        if previous_period is not None and previous_period == current_period:
            return True
    return False


def _meal_time_category_priority(
    place: Place,
    visit_time: time,
) -> int:
    minute = visit_time.hour * 60 + visit_time.minute
    if 7 * 60 <= minute <= 10 * 60 + 30:
        if place.category != PlaceCategory.RESTAURANT:
            return 2
        return 0 if place.lcls_system2 == "FD03" else 1
    if 11 * 60 <= minute <= 14 * 60 or 17 * 60 <= minute <= 20 * 60:
        return 0 if place.category == PlaceCategory.RESTAURANT else 1
    return (
        0
        if place.category
        in {
            PlaceCategory.TOURIST_SPOT,
            PlaceCategory.CAFE,
            PlaceCategory.CULTURAL_FACILITY,
        }
        else 1
    )


def _meal_period(visit_time: time) -> str | None:
    minute = visit_time.hour * 60 + visit_time.minute
    if 7 * 60 <= minute <= 10 * 60 + 30:
        return "BREAKFAST"
    if 11 * 60 <= minute <= 14 * 60:
        return "LUNCH"
    if 17 * 60 <= minute <= 20 * 60:
        return "DINNER"
    return None


MEAL_WINDOWS = (
    ("BREAKFAST", time(7, 0), time(10, 30)),
    ("LUNCH", time(11, 0), time(14, 0)),
    ("DINNER", time(17, 0), time(20, 0)),
)


def _place_for_next_meal_period(
    place: Place,
    covered_periods: set[str],
    *,
    target_date: date,
    available_start: datetime,
    available_end: datetime,
) -> Place | None:
    """식당을 아직 비어 있는 다음 식사 시간대로 제한해 대기 배치한다."""

    if place.category != PlaceCategory.RESTAURANT:
        return place
    if _is_closed(place, target_date):
        return None

    weekday = list(Weekday)[target_date.weekday()]
    real_open, real_close = _hours_for_date(place, target_date)
    parsed_open = _parse_time(real_open)
    parsed_close = _parse_time(real_close)

    for period, window_open, window_close in MEAL_WINDOWS:
        if period in covered_periods:
            continue
        open_at = max(
            datetime.combine(target_date, window_open, available_start.tzinfo),
            available_start,
        )
        close_at = min(
            datetime.combine(target_date, window_close, available_end.tzinfo),
            available_end,
        )
        if parsed_open is not None:
            open_at = max(
                open_at,
                datetime.combine(target_date, parsed_open, open_at.tzinfo),
            )
        if parsed_close is not None:
            close_at = min(
                close_at,
                datetime.combine(target_date, parsed_close, close_at.tzinfo),
            )
        if open_at + timedelta(minutes=place.default_stay_minutes) > close_at:
            continue
        return place.model_copy(
            update={
                "business_hours_status": BusinessRuleStatus.PARSED,
                "business_hours_rules": [
                    BusinessHoursRule(
                        weekdays=[weekday],
                        open_time=open_at.strftime("%H:%M"),
                        close_time=close_at.strftime("%H:%M"),
                    )
                ],
            }
        )
    return None


def _covered_meal_periods(visits) -> set[str]:
    """일정에 실제 식당 방문이 배치된 아침·점심·저녁 구간을 반환합니다."""

    covered: set[str] = set()
    for visit in visits:
        if visit.place.category != PlaceCategory.RESTAURANT:
            continue
        period = _meal_period(visit.start.time())
        if period is not None:
            covered.add(period)
    return covered


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
    if target_date == trip.trip_start_at.date():
        start_id = "arrival"
        available_start = trip.trip_start_at + timedelta(
            minutes=DEFAULT_ANCHOR_MINUTES
        )
    if target_date == trip.game_anchor.game_start_at.date():
        end_id = "stadium"
        available_end = trip.game_anchor.game_start_at - timedelta(
            minutes=trip.game_anchor.required_arrival_minutes
        )
    elif target_date == trip.trip_end_at.date():
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
    travel_distance: int = 0,
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
        travel_distance_meters_from_previous=travel_distance,
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

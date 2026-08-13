from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable

from app.algorithms.travel_time import TravelTimeMatrix
from app.models.place import Place


@dataclass(frozen=True)
class ScheduledVisit:
    place: Place
    start: datetime
    end: datetime
    travel_minutes: int


HoursResolver = Callable[[Place, date], tuple[str | None, str | None]]
ClosedChecker = Callable[[Place, date], bool]
TimeParser = Callable[[str | None], object | None]
TRANSFER_BUFFER_MINUTES = 15


def transfer_buffer(origin_id: str, destination_id: str | None) -> int:
    if destination_id is None or origin_id == destination_id:
        return 0
    return TRANSFER_BUFFER_MINUTES


def route_travel_minutes(
    start_id: str,
    route: list[Place],
    end_id: str | None,
    matrix: TravelTimeMatrix,
) -> int:
    total = 0
    previous = start_id
    for place in route:
        total += matrix.get(previous, place.place_id)
        previous = place.place_id
    if end_id is not None:
        total += matrix.get(previous, end_id)
    return total


def simulate_route(
    route: list[Place],
    *,
    target_date: date,
    start_id: str,
    end_id: str | None,
    available_start: datetime,
    available_end: datetime,
    matrix: TravelTimeMatrix,
    hours_for_date: HoursResolver,
    is_closed: ClosedChecker,
    parse_time: TimeParser,
) -> list[ScheduledVisit] | None:
    cursor = available_start
    previous = start_id
    visits: list[ScheduledVisit] = []
    for place in route:
        if is_closed(place, target_date):
            return None
        travel = matrix.get(previous, place.place_id)
        buffer = transfer_buffer(previous, place.place_id)
        start = cursor + timedelta(minutes=travel + buffer)
        opening, closing = hours_for_date(place, target_date)
        opening_time = parse_time(opening)
        if opening_time is not None:
            start = max(
                start,
                datetime.combine(target_date, opening_time, start.tzinfo),
            )
        end = start + timedelta(minutes=place.default_stay_minutes)
        closing_time = parse_time(closing)
        if closing_time is not None and end > datetime.combine(
            target_date, closing_time, end.tzinfo
        ):
            return None
        admission_time = parse_time(place.admission_deadline_time)
        if (
            place.admission_deadline_status == "PARSED"
            and admission_time is not None
            and start > datetime.combine(
                target_date, admission_time, start.tzinfo
            )
        ):
            return None
        visits.append(ScheduledVisit(place, start, end, travel))
        cursor, previous = end, place.place_id

    tail = matrix.get(previous, end_id) if end_id is not None else 0
    tail += transfer_buffer(previous, end_id)
    if cursor + timedelta(minutes=tail) > available_end:
        return None
    return visits


def greedy_insertion(
    candidates: list[Place],
    *,
    target_date: date,
    start_id: str,
    end_id: str | None,
    available_start: datetime,
    available_end: datetime,
    matrix: TravelTimeMatrix,
    is_required: Callable[[Place], bool],
    candidate_priority: Callable[[Place], float],
    hours_for_date: HoursResolver,
    is_closed: ClosedChecker,
    parse_time: TimeParser,
) -> tuple[list[Place], list[Place]]:
    route: list[Place] = []
    rejected: list[Place] = []
    ordered = sorted(
        candidates,
        key=lambda place: (
            not is_required(place),
            candidate_priority(place),
            place.place_id,
        ),
    )
    for place in ordered:
        best_route = None
        best_cost = None
        current_cost = route_travel_minutes(start_id, route, end_id, matrix)
        for index in range(len(route) + 1):
            proposed = [*route[:index], place, *route[index:]]
            if simulate_route(
                proposed,
                target_date=target_date,
                start_id=start_id,
                end_id=end_id,
                available_start=available_start,
                available_end=available_end,
                matrix=matrix,
                hours_for_date=hours_for_date,
                is_closed=is_closed,
                parse_time=parse_time,
            ) is None:
                continue
            increase = route_travel_minutes(start_id, proposed, end_id, matrix) - current_cost
            if best_cost is None or increase < best_cost:
                best_cost, best_route = increase, proposed
        if best_route is None:
            rejected.append(place)
        else:
            route = best_route
    return route, rejected


def improve_route_2opt(
    route: list[Place],
    **kwargs,
) -> list[Place]:
    if len(route) < 3:
        return route
    matrix = kwargs["matrix"]
    start_id, end_id = kwargs["start_id"], kwargs["end_id"]
    best = list(route)
    improved = True
    while improved:
        improved = False
        best_cost = route_travel_minutes(start_id, best, end_id, matrix)
        for left in range(len(best) - 1):
            for right in range(left + 1, len(best)):
                candidate = best[:left] + list(reversed(best[left:right + 1])) + best[right + 1:]
                cost = route_travel_minutes(start_id, candidate, end_id, matrix)
                if cost >= best_cost:
                    continue
                if simulate_route(candidate, **kwargs) is None:
                    continue
                best, best_cost, improved = candidate, cost, True
                break
            if improved:
                break
    return best

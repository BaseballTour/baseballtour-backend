from datetime import date

from app.models.itinerary import DayType


def is_arrival_day(target: date, trip_start: date) -> bool:
    return target == trip_start


def is_game_day(target: date, game_date: date) -> bool:
    return target == game_date


def is_departure_day(target: date, trip_end: date) -> bool:
    return target == trip_end


def is_free_day(
    target: date,
    trip_start: date,
    trip_end: date,
    game_date: date,
) -> bool:
    return (
        trip_start < target < trip_end
        and not is_game_day(target, game_date)
    )


def classify_day(
    target: date,
    trip_start: date,
    trip_end: date,
    game_date: date,
) -> DayType:
    """단일 dayType이 필요할 때 경기일을 가장 높은 우선순위로 둔다."""
    if is_game_day(target, game_date):
        return DayType.GAME_DAY
    if is_arrival_day(target, trip_start):
        return DayType.ARRIVAL_DAY
    if is_departure_day(target, trip_end):
        return DayType.DEPARTURE_DAY
    if is_free_day(target, trip_start, trip_end, game_date):
        return DayType.NON_GAME_DAY
    raise ValueError("여행 기간 밖의 날짜입니다.")

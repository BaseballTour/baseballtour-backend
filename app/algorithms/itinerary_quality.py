from __future__ import annotations

from datetime import datetime, time, timedelta

from app.models.itinerary import (
    ItineraryItemAddedBy,
    ItineraryItemType,
    ItineraryQualityCode,
    ItineraryQualityIssue,
    ItineraryQualitySeverity,
    ItineraryQualityStatus,
    ItineraryQualitySummary,
    ItineraryResult,
    TravelTimeSource,
    TripInput,
)
from app.models.place import BusinessRuleStatus, PlaceCategory


MEAL_WINDOWS = {
    "BREAKFAST": (time(7, 0), time(10, 30)),
    "LUNCH": (time(11, 30), time(14, 0)),
    "DINNER": (time(17, 30), time(20, 30)),
}
MINIMUM_MEAL_SLOT_MINUTES = 60
LONG_IDLE_GAP_MINUTES = 150


def evaluate_itinerary_quality(
    trip: TripInput,
    result: ItineraryResult,
) -> ItineraryQualitySummary:
    """일정의 구조 오류와 사용자에게 알려야 할 품질 위험을 계산한다."""

    issues: list[ItineraryQualityIssue] = []
    for day in result.days:
        items = sorted(day.items, key=lambda item: item.scheduled_start_at)
        for item in items:
            if (
                item.scheduled_start_at < trip.trip_start_at
                or item.scheduled_end_at > trip.trip_end_at
            ):
                issues.append(_issue(
                    ItineraryQualityCode.ITEM_OUTSIDE_TRIP_PERIOD,
                    ItineraryQualitySeverity.ERROR,
                    "일정 항목이 여행 기간을 벗어났습니다.",
                    day.date, item,
                ))
            if (
                item.item_type == ItineraryItemType.PLACE
                and item.business_hours_status
                in {
                    BusinessRuleStatus.MISSING.value,
                    BusinessRuleStatus.UNPARSABLE.value,
                    BusinessRuleStatus.COMPLEX.value,
                }
            ):
                actor = (
                    "사용자가 선택한 장소"
                    if item.added_by == ItineraryItemAddedBy.USER
                    else "자동 추천 장소"
                )
                issues.append(_issue(
                    ItineraryQualityCode.BUSINESS_HOURS_UNVERIFIED,
                    ItineraryQualitySeverity.WARNING,
                    f"{actor}의 영업시간을 확인해야 합니다.",
                    day.date, item,
                ))
            if item.travel_time_source == TravelTimeSource.ESTIMATED:
                issues.append(_issue(
                    ItineraryQualityCode.ESTIMATED_TRAVEL_TIME,
                    ItineraryQualitySeverity.WARNING,
                    "실제 경로 대신 추정 이동시간을 사용했습니다.",
                    day.date, item,
                ))

        for previous, current in zip(items, items[1:]):
            if current.scheduled_start_at < previous.scheduled_end_at:
                issues.append(_issue(
                    ItineraryQualityCode.ITEM_TIME_OVERLAP,
                    ItineraryQualitySeverity.ERROR,
                    "일정 항목 시간이 서로 겹칩니다.",
                    day.date, current,
                ))
            gap = current.scheduled_start_at - previous.scheduled_end_at
            idle = gap - timedelta(
                minutes=current.travel_minutes_from_previous
                + current.transfer_buffer_minutes
            )
            if idle >= timedelta(minutes=LONG_IDLE_GAP_MINUTES):
                issues.append(_issue(
                    ItineraryQualityCode.LONG_IDLE_GAP,
                    ItineraryQualitySeverity.WARNING,
                    f"이동시간을 제외하고 {int(idle.total_seconds() // 60)}분의 공백이 있습니다.",
                    day.date, current,
                ))

        _append_meal_warnings(trip, day.date, items, issues)

    included_dates = {day.date for day in result.days}
    required_types = set()
    if trip.trip_start_at.date() in included_dates:
        required_types.add(ItineraryItemType.ARRIVAL_POINT)
    if trip.trip_end_at.date() in included_dates:
        required_types.add(ItineraryItemType.DEPARTURE_POINT)
    if trip.game_anchor.game_start_at.date() in included_dates:
        required_types.add(ItineraryItemType.STADIUM)
    existing_types = {
        item.item_type for day in result.days for item in day.items
    }
    for missing in sorted(required_types - existing_types, key=lambda value: value.value):
        issues.append(ItineraryQualityIssue(
            code=ItineraryQualityCode.REQUIRED_ANCHOR_MISSING,
            severity=ItineraryQualitySeverity.ERROR,
            message=f"필수 일정 항목 {missing.value}이 없습니다.",
        ))

    stadium = next(
        (
            item
            for day in result.days
            for item in day.items
            if item.item_type == ItineraryItemType.STADIUM
        ),
        None,
    )
    expected_stadium_at = trip.game_anchor.game_start_at - timedelta(
        minutes=trip.game_anchor.required_arrival_minutes
    )
    if stadium is not None and stadium.scheduled_start_at != expected_stadium_at:
        issues.append(_issue(
            ItineraryQualityCode.STADIUM_ARRIVAL_TIME_INVALID,
            ItineraryQualitySeverity.ERROR,
            "경기장 도착시각이 경기 시작 전 필수 도착 조건과 다릅니다.",
            stadium.scheduled_start_at.date(), stadium,
        ))

    warning_count = sum(
        issue.severity == ItineraryQualitySeverity.WARNING for issue in issues
    )
    error_count = sum(
        issue.severity == ItineraryQualitySeverity.ERROR for issue in issues
    )
    score = max(0, 100 - warning_count * 4 - error_count * 25)
    status = (
        ItineraryQualityStatus.FAIL
        if error_count
        else ItineraryQualityStatus.WARNING
        if warning_count
        else ItineraryQualityStatus.PASS
    )
    return ItineraryQualitySummary(
        status=status,
        score=score,
        warning_count=warning_count,
        error_count=error_count,
        issues=issues,
    )


def _append_meal_warnings(trip, target_date, items, issues) -> None:
    day_start = max(
        trip.trip_start_at,
        datetime.combine(target_date, time(7, 0), trip.trip_start_at.tzinfo),
    )
    day_end = min(
        trip.trip_end_at,
        datetime.combine(target_date, time(20, 30), trip.trip_start_at.tzinfo),
    )
    for period, (window_start, window_end) in MEAL_WINDOWS.items():
        start = max(day_start, datetime.combine(target_date, window_start, day_start.tzinfo))
        end = min(day_end, datetime.combine(target_date, window_end, day_end.tzinfo))
        if int((end - start).total_seconds() // 60) < MINIMUM_MEAL_SLOT_MINUTES:
            continue
        restaurant_exists = any(
            item.item_type == ItineraryItemType.PLACE
            and item.category == PlaceCategory.RESTAURANT
            and start <= item.scheduled_start_at <= end
            for item in items
        )
        free_minutes = int((end - start).total_seconds() // 60)
        for item in items:
            occupied_start = item.scheduled_start_at - timedelta(
                minutes=item.travel_minutes_from_previous
                + item.transfer_buffer_minutes
            )
            overlap_start = max(start, occupied_start)
            overlap_end = min(end, item.scheduled_end_at)
            if overlap_end > overlap_start:
                free_minutes -= int((overlap_end - overlap_start).total_seconds() // 60)
        if not restaurant_exists and free_minutes >= MINIMUM_MEAL_SLOT_MINUTES:
            issues.append(ItineraryQualityIssue(
                code=ItineraryQualityCode.MEAL_MISSING,
                severity=ItineraryQualitySeverity.WARNING,
                message=f"{period} 시간대에 식사 장소가 배치되지 않았습니다.",
                date=target_date,
                meal_period=period,
            ))


def _issue(code, severity, message, target_date, item):
    return ItineraryQualityIssue(
        code=code,
        severity=severity,
        message=message,
        date=target_date,
        item_id=getattr(item, "item_id", None),
        place_id=item.place_id,
    )

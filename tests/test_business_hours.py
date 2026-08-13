from datetime import date

from app.algorithms.itinerary_generator import _hours_for_date, _is_closed
from app.external.tour_api.business_hours import (
    parse_admission_deadline,
    parse_business_hours,
    parse_closed_days,
)
from app.models.place import BusinessRuleStatus, Place, PlaceSource


def place_with(**updates) -> Place:
    values = dict(
        place_id="tour_1", name="테스트", latitude=37.5, longitude=127.0,
        source=PlaceSource.TOUR_API, source_content_id="1",
    )
    values.update(updates)
    return Place(**values)


def test_parses_weekday_and_weekend_hours() -> None:
    status, text, rules = parse_business_hours(
        "평일 09:00~18:00 / 주말 10:00~17:00"
    )
    assert status == BusinessRuleStatus.PARSED
    assert text is not None
    assert len(rules) == 2
    place = place_with(business_hours_status=status, business_hours_text=text, business_hours_rules=rules)
    assert _hours_for_date(place, date(2026, 8, 15)) == ("10:00", "17:00")
    assert _hours_for_date(place, date(2026, 8, 17)) == ("09:00", "18:00")
    dumped_rule = place.model_dump()["businessHoursRules"][0]
    assert dumped_rule["openTime"] == "09:00"
    assert dumped_rule["closeTime"] == "18:00"


def test_parses_korean_am_pm_hours() -> None:
    status, _, rules = parse_business_hours("매일 오전 9시~오후 6시")
    assert status == BusinessRuleStatus.PARSED
    assert (rules[0].open_time, rules[0].close_time) == ("09:00", "18:00")


def test_complex_hours_keep_text_but_have_no_rules() -> None:
    status, text, rules = parse_business_hours("평일 09:00~18:00 (공휴일 별도)")
    assert status == BusinessRuleStatus.COMPLEX
    assert text == "평일 09:00~18:00 (공휴일 별도)"
    assert rules == []


def test_parses_hours_and_admission_deadline_separately() -> None:
    raw = "매일 09:00~18:00 (입장 마감 17:00)"
    status, text, rules = parse_business_hours(raw)
    deadline_status, deadline_text, deadline = parse_admission_deadline(raw)

    assert status == BusinessRuleStatus.PARSED
    assert text == raw
    assert (rules[0].open_time, rules[0].close_time) == ("09:00", "18:00")
    assert deadline_status == BusinessRuleStatus.PARSED
    assert deadline_text == raw
    assert deadline == "17:00"


def test_missing_admission_deadline_is_not_inferred() -> None:
    status, text, deadline = parse_admission_deadline("매일 09:00~18:00")

    assert status == BusinessRuleStatus.MISSING
    assert text is None
    assert deadline is None


def test_parses_weekend_closure_for_algorithm() -> None:
    status, text, days = parse_closed_days("매주 토요일, 일요일")
    place = place_with(closed_days_status=status, closed_days_text=text, closed_weekdays=days)
    assert _is_closed(place, date(2026, 8, 15)) is True
    assert _is_closed(place, date(2026, 8, 17)) is False


def test_complex_closure_is_not_applied_to_algorithm() -> None:
    status, text, days = parse_closed_days("매월 첫째·셋째 월요일")
    assert status == BusinessRuleStatus.COMPLEX
    place = place_with(closed_days_status=status, closed_days_text=text, closed_weekdays=days)
    assert _is_closed(place, date(2026, 8, 17)) is False

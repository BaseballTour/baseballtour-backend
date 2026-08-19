import re

from app.models.place import BusinessHoursRule, BusinessRuleStatus, Weekday

ALL_DAYS = list(Weekday)
DAY_MAP = dict(zip("월화수목금토일", ALL_DAYS))
COMPLEX = ("공휴일", "성수기", "비수기", "시즌", "첫째", "둘째", "셋째", "넷째", "마지막", "브레이크", "라스트오더")


def _clean(value):
    if not value or not str(value).strip():
        return None
    text = re.sub(r"<br\s*/?>", " / ", str(value), flags=re.I)
    return re.sub(r"<[^>]+>", " ", text).strip()


def _times(text):
    found = []
    for match in re.finditer(r"(오전|오후)\s*(\d{1,2})\s*시(?:\s*(\d{1,2})\s*분)?|(\d{1,2}):([0-5]\d)", text):
        if match[4]:
            hour, minute = int(match[4]), int(match[5])
        else:
            hour, minute = int(match[2]), int(match[3] or 0)
            if match[1] == "오후" and hour < 12:
                hour += 12
            if match[1] == "오전" and hour == 12:
                hour = 0
        found.append(f"{hour:02d}:{minute:02d}")
    return found


def _days(text):
    if "평일" in text:
        return ALL_DAYS[:5]
    if "주말" in text:
        return ALL_DAYS[5:]
    if "매일" in text or "연중" in text:
        return ALL_DAYS
    match = re.search(r"([월화수목금토일])(?:요일)?\s*[~-]\s*([월화수목금토일])", text)
    if match:
        start, end = ALL_DAYS.index(DAY_MAP[match[1]]), ALL_DAYS.index(DAY_MAP[match[2]])
        return ALL_DAYS[start:end + 1] if start <= end else ALL_DAYS[start:] + ALL_DAYS[:end + 1]
    result = [day for token, day in DAY_MAP.items() if re.search(fr"{token}(?:요일)?", text)]
    return result or ALL_DAYS


def parse_business_hours(value):
    text = _clean(value)
    if text is None:
        return BusinessRuleStatus.MISSING, None, []
    hours_text = re.sub(
        r"(?:입장\s*마감|매표\s*마감)\s*(?:(?:오전|오후)\s*\d{1,2}\s*시(?:\s*\d{1,2}\s*분)?|\d{1,2}:[0-5]\d)",
        "",
        text,
    ).strip(" ()[],-")
    if any(marker in hours_text for marker in COMPLEX):
        return BusinessRuleStatus.COMPLEX, text, []
    if "24시간" in text or "상시 개방" in text or "상시개방" in text:
        return BusinessRuleStatus.PARSED, text, [BusinessHoursRule(weekdays=ALL_DAYS, open_time="00:00", close_time="23:59")]
    rules = []
    for part in [x.strip() for x in re.split(r"[/\n;]", hours_text) if x.strip()]:
        times = _times(part)
        if len(times) != 2:
            status = BusinessRuleStatus.COMPLEX if len(times) > 2 else BusinessRuleStatus.UNPARSABLE
            return status, text, []
        if times[1] <= times[0]:
            return BusinessRuleStatus.COMPLEX, text, []
        rules.append(BusinessHoursRule(weekdays=_days(part), open_time=times[0], close_time=times[1]))
    return BusinessRuleStatus.PARSED, text, rules


def parse_admission_deadline(value):
    """명시적인 입장/매표 마감 시각 하나만 안전하게 해석한다."""
    text = _clean(value)
    if text is None:
        return BusinessRuleStatus.MISSING, None, None
    matches = re.findall(
        r"(?:입장\s*마감|매표\s*마감)\s*((?:오전|오후)\s*\d{1,2}\s*시(?:\s*\d{1,2}\s*분)?|\d{1,2}:[0-5]\d)",
        text,
    )
    if not matches:
        return BusinessRuleStatus.MISSING, None, None
    times = [_times(match) for match in matches]
    parsed = [values[0] for values in times if len(values) == 1]
    if len(parsed) != 1 or len(matches) != 1:
        return BusinessRuleStatus.COMPLEX, text, None
    return BusinessRuleStatus.PARSED, text, parsed[0]


def parse_closed_days(value):
    text = _clean(value)
    if text is None:
        return BusinessRuleStatus.MISSING, None, []
    if "연중무휴" in text or text in {"없음", "무휴"}:
        return BusinessRuleStatus.PARSED, text, []
    if any(marker in text for marker in COMPLEX):
        return BusinessRuleStatus.COMPLEX, text, []
    days = _days(text)
    if days == ALL_DAYS and not any(token in text for token in DAY_MAP):
        return BusinessRuleStatus.UNPARSABLE, text, []
    return BusinessRuleStatus.PARSED, text, days

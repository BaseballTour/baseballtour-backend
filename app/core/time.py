from datetime import datetime
from zoneinfo import ZoneInfo


KOREA_TIMEZONE = ZoneInfo("Asia/Seoul")


def to_korea_datetime(value: datetime) -> datetime:
    """시간대가 있는 datetime을 동일한 절대시각의 한국시간으로 바꾼다."""
    if value.tzinfo is None:
        return value
    return value.astimezone(KOREA_TIMEZONE)


def to_korea_isoformat(value: datetime) -> str:
    """API datetime을 ISO 8601 한국시간 문자열로 직렬화한다."""
    return to_korea_datetime(value).isoformat()

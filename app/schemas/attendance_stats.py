from enum import Enum

from pydantic import Field

from app.schemas.base import ApiModel


class AttendanceWeekday(str, Enum):
    """경기 시작일 기준 요일."""

    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"


class AttendanceWeekdayStatsResponse(ApiModel):
    """요일별 직관 통계."""

    weekday: AttendanceWeekday
    attendance_count: int = Field(ge=0)
    win_count: int = Field(ge=0)
    loss_count: int = Field(ge=0)
    draw_count: int = Field(ge=0)
    win_rate: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description=(
            "점수가 확인된 경기 기준 승률(%). "
            "집계 가능한 경기가 없으면 null"
        ),
    )


class AttendanceStatsResponse(ApiModel):
    """마이페이지 직관 통계 응답."""

    away_trip_count: int = Field(
        ge=0,
        description="응원팀이 원정팀이었던 직관 횟수",
    )
    away_win_count: int = Field(
        ge=0,
        description="원정 직관 승리 횟수",
    )
    home_attendance_count: int = Field(
        ge=0,
        description="응원팀이 홈팀이었던 직관 횟수",
    )
    home_win_rate: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="홈 직관 승률(%)",
    )
    away_win_rate: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="원정 직관 승률(%)",
    )
    recent_10_attendance_count: int = Field(
        ge=0,
        description="최근 직관 통계에 포함된 경기 수. 최대 10",
    )
    recent_10_win_rate: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="최근 최대 10번 직관의 승률(%)",
    )
    weekday_stats: list[
        AttendanceWeekdayStatsResponse
    ]

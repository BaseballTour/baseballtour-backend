from app.schemas.attendance_log import (
    AttendanceLogGameResult,
    AttendanceLogHomeSide,
)


def resolve_home_side(
    *,
    support_team_id: str | None,
    home_team_id: str,
    away_team_id: str,
) -> AttendanceLogHomeSide:
    """응원팀 기준 홈/원정 여부를 계산합니다."""

    if support_team_id == home_team_id:
        return AttendanceLogHomeSide.HOME

    if support_team_id == away_team_id:
        return AttendanceLogHomeSide.AWAY

    return AttendanceLogHomeSide.OTHER


def resolve_game_result(
    *,
    home_side: AttendanceLogHomeSide,
    home_score: int | None,
    away_score: int | None,
) -> AttendanceLogGameResult | None:
    """응원팀 기준 경기 결과를 계산합니다."""

    if (
        home_side == AttendanceLogHomeSide.OTHER
        or home_score is None
        or away_score is None
    ):
        return None

    if home_score == away_score:
        return AttendanceLogGameResult.DRAW

    home_won = home_score > away_score

    if home_side == AttendanceLogHomeSide.HOME:
        return (
            AttendanceLogGameResult.WIN
            if home_won
            else AttendanceLogGameResult.LOSS
        )

    return (
        AttendanceLogGameResult.LOSS
        if home_won
        else AttendanceLogGameResult.WIN
    )

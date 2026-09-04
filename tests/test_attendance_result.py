import pytest

from app.schemas.attendance_log import (
    AttendanceLogGameResult,
    AttendanceLogHomeSide,
)
from app.services.attendance_result import (
    resolve_game_result,
    resolve_home_side,
)


@pytest.mark.parametrize(
    (
        "support_team_id",
        "expected",
    ),
    [
        ("home", AttendanceLogHomeSide.HOME),
        ("away", AttendanceLogHomeSide.AWAY),
        ("other", AttendanceLogHomeSide.OTHER),
        (None, AttendanceLogHomeSide.OTHER),
    ],
)
def test_resolve_home_side(
    support_team_id,
    expected,
) -> None:
    assert (
        resolve_home_side(
            support_team_id=support_team_id,
            home_team_id="home",
            away_team_id="away",
        )
        == expected
    )


@pytest.mark.parametrize(
    (
        "side",
        "home_score",
        "away_score",
        "expected",
    ),
    [
        (
            AttendanceLogHomeSide.HOME,
            5,
            3,
            AttendanceLogGameResult.WIN,
        ),
        (
            AttendanceLogHomeSide.HOME,
            3,
            5,
            AttendanceLogGameResult.LOSS,
        ),
        (
            AttendanceLogHomeSide.AWAY,
            3,
            5,
            AttendanceLogGameResult.WIN,
        ),
        (
            AttendanceLogHomeSide.AWAY,
            5,
            3,
            AttendanceLogGameResult.LOSS,
        ),
        (
            AttendanceLogHomeSide.HOME,
            3,
            3,
            AttendanceLogGameResult.DRAW,
        ),
        (
            AttendanceLogHomeSide.OTHER,
            5,
            3,
            None,
        ),
        (
            AttendanceLogHomeSide.HOME,
            None,
            None,
            None,
        ),
    ],
)
def test_resolve_game_result(
    side,
    home_score,
    away_score,
    expected,
) -> None:
    assert (
        resolve_game_result(
            home_side=side,
            home_score=home_score,
            away_score=away_score,
        )
        == expected
    )

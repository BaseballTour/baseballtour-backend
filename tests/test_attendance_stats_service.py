from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

from app.schemas.attendance_stats import (
    AttendanceWeekday,
)
from app.services.attendance_stats_service import (
    AttendanceStatsService,
)


USER_ID = "firebase-user-123"


def make_log(
    *,
    game_id: str,
    support_team_id: str | None = "doosan",
):
    return SimpleNamespace(
        game_id=game_id,
        support_team_id=support_team_id,
    )


def make_game(
    *,
    game_id: str,
    day: int,
    home_team_id: str,
    away_team_id: str,
    home_score: int | None,
    away_score: int | None,
):
    return SimpleNamespace(
        game_id=game_id,
        home_team_id=home_team_id,
        away_team_id=away_team_id,
        game_start_at=datetime(
            2026,
            9,
            day,
            18,
            30,
            tzinfo=timezone.utc,
        ),
        home_score=home_score,
        away_score=away_score,
    )


def test_get_stats_aggregates_attendance_results() -> None:
    attendance_repository = Mock()
    game_repository = Mock()

    attendance_repository.get_by_user_id.return_value = [
        # HOME 승
        make_log(game_id="g1"),
        # AWAY 패
        make_log(game_id="g2"),
        # AWAY 무
        make_log(game_id="g3"),
        # legacy snapshot -> 현재 두산으로 fallback
        make_log(
            game_id="g4",
            support_team_id=None,
        ),
        # OTHER -> 통계 제외
        make_log(
            game_id="g5",
            support_team_id="lotte",
        ),
        # HOME, 아직 점수 없음
        make_log(game_id="g6"),
    ]

    games = {
        "g1": make_game(
            game_id="g1",
            day=7,
            home_team_id="doosan",
            away_team_id="lg",
            home_score=5,
            away_score=3,
        ),
        "g2": make_game(
            game_id="g2",
            day=8,
            home_team_id="lg",
            away_team_id="doosan",
            home_score=4,
            away_score=2,
        ),
        "g3": make_game(
            game_id="g3",
            day=9,
            home_team_id="lg",
            away_team_id="doosan",
            home_score=2,
            away_score=2,
        ),
        "g4": make_game(
            game_id="g4",
            day=10,
            home_team_id="kt",
            away_team_id="doosan",
            home_score=1,
            away_score=3,
        ),
        "g5": make_game(
            game_id="g5",
            day=11,
            home_team_id="doosan",
            away_team_id="lg",
            home_score=5,
            away_score=2,
        ),
        "g6": make_game(
            game_id="g6",
            day=12,
            home_team_id="doosan",
            away_team_id="lg",
            home_score=None,
            away_score=None,
        ),
    }

    game_repository.get_by_id.side_effect = (
        lambda game_id: games[game_id]
    )

    service = AttendanceStatsService(
        attendance_log_repository=(
            attendance_repository
        ),
        game_repository=game_repository,
    )

    result = service.get_stats(
        user_id=USER_ID,
        current_support_team_id="doosan",
    )

    assert result.away_trip_count == 3
    assert result.away_win_count == 1
    assert result.home_attendance_count == 2

    # HOME은 점수가 있는 g1만 승률 분모에 포함
    assert result.home_win_rate == 100.0

    # AWAY: 1승 1패 1무
    assert result.away_win_rate == 33.33

    # OTHER 제외, HOME/AWAY 5경기
    assert result.recent_10_attendance_count == 5

    # 최근 5경기 중 결과 확정 4경기:
    # 2승 1패 1무
    assert result.recent_10_win_rate == 50.0

    assert len(result.weekday_stats) == 7

    monday = next(
        item
        for item in result.weekday_stats
        if item.weekday
        == AttendanceWeekday.MONDAY
    )

    assert monday.attendance_count == 1
    assert monday.win_count == 1
    assert monday.win_rate == 100.0


def test_get_stats_returns_null_rates_without_scores() -> None:
    attendance_repository = Mock()
    game_repository = Mock()

    attendance_repository.get_by_user_id.return_value = [
        make_log(game_id="g1"),
    ]

    game_repository.get_by_id.return_value = (
        make_game(
            game_id="g1",
            day=7,
            home_team_id="doosan",
            away_team_id="lg",
            home_score=None,
            away_score=None,
        )
    )

    service = AttendanceStatsService(
        attendance_log_repository=(
            attendance_repository
        ),
        game_repository=game_repository,
    )

    result = service.get_stats(
        user_id=USER_ID,
        current_support_team_id="doosan",
    )

    assert result.home_attendance_count == 1
    assert result.home_win_rate is None
    assert result.recent_10_win_rate is None


def test_recent_10_uses_latest_game_start_times() -> None:
    attendance_repository = Mock()
    game_repository = Mock()

    logs = []
    games = {}

    for day in range(1, 13):
        game_id = f"g{day}"

        logs.append(
            make_log(game_id=game_id)
        )

        # 1~2일 경기만 승리, 3~12일은 패배.
        # 최근 10경기는 3~12일이므로 승률 0%여야 합니다.
        games[game_id] = make_game(
            game_id=game_id,
            day=day,
            home_team_id="doosan",
            away_team_id="lg",
            home_score=(
                5 if day <= 2 else 1
            ),
            away_score=(
                1 if day <= 2 else 5
            ),
        )

    attendance_repository.get_by_user_id.return_value = (
        logs
    )

    game_repository.get_by_id.side_effect = (
        lambda game_id: games[game_id]
    )

    service = AttendanceStatsService(
        attendance_log_repository=(
            attendance_repository
        ),
        game_repository=game_repository,
    )

    result = service.get_stats(
        user_id=USER_ID,
        current_support_team_id="doosan",
    )

    assert result.home_attendance_count == 12
    assert result.home_win_rate == 16.67
    assert result.recent_10_attendance_count == 10
    assert result.recent_10_win_rate == 0.0

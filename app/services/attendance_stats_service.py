from dataclasses import dataclass
from datetime import datetime

from app.repositories.attendance_log_repository import (
    AttendanceLogRepository,
)
from app.repositories.game_repository import GameRepository
from app.schemas.attendance_log import (
    AttendanceLogGameResult,
    AttendanceLogHomeSide,
)
from app.schemas.attendance_stats import (
    AttendanceStatsResponse,
    AttendanceWeekday,
    AttendanceWeekdayStatsResponse,
)
from app.services.attendance_result import (
    resolve_game_result,
    resolve_home_side,
)


@dataclass
class _AttendanceGame:
    game_start_at: datetime
    home_side: AttendanceLogHomeSide
    result: AttendanceLogGameResult | None


class AttendanceStatsService:
    """직관 로그를 기반으로 마이페이지 통계를 계산합니다."""

    WEEKDAYS = (
        AttendanceWeekday.MONDAY,
        AttendanceWeekday.TUESDAY,
        AttendanceWeekday.WEDNESDAY,
        AttendanceWeekday.THURSDAY,
        AttendanceWeekday.FRIDAY,
        AttendanceWeekday.SATURDAY,
        AttendanceWeekday.SUNDAY,
    )

    def __init__(
        self,
        attendance_log_repository: (
            AttendanceLogRepository | None
        ) = None,
        game_repository: GameRepository | None = None,
    ) -> None:
        self._attendance_log_repository = (
            attendance_log_repository
            or AttendanceLogRepository()
        )
        self._game_repository = (
            game_repository
            or GameRepository()
        )

    def get_stats(
        self,
        *,
        user_id: str,
        current_support_team_id: str,
    ) -> AttendanceStatsResponse:
        logs = (
            self._attendance_log_repository
            .get_by_user_id(user_id)
        )

        attendance_games: list[_AttendanceGame] = []

        for log in logs:
            game = self._game_repository.get_by_id(
                log.game_id
            )

            # 삭제되었거나 비정상적으로 연결이 끊긴
            # 경기 데이터는 통계에서 제외합니다.
            if game is None:
                continue

            support_team_id = (
                log.support_team_id
                if log.support_team_id is not None
                else current_support_team_id
            )

            home_side = resolve_home_side(
                support_team_id=support_team_id,
                home_team_id=game.home_team_id,
                away_team_id=game.away_team_id,
            )

            # 응원팀이 참가하지 않은 경기는
            # 개인 응원팀 승률 통계에서 제외합니다.
            if home_side == AttendanceLogHomeSide.OTHER:
                continue

            result = resolve_game_result(
                home_side=home_side,
                home_score=game.home_score,
                away_score=game.away_score,
            )

            attendance_games.append(
                _AttendanceGame(
                    game_start_at=game.game_start_at,
                    home_side=home_side,
                    result=result,
                )
            )

        attendance_games.sort(
            key=lambda item: item.game_start_at,
            reverse=True,
        )

        home_games = [
            item
            for item in attendance_games
            if item.home_side
            == AttendanceLogHomeSide.HOME
        ]
        away_games = [
            item
            for item in attendance_games
            if item.home_side
            == AttendanceLogHomeSide.AWAY
        ]

        recent_games = attendance_games[:10]

        return AttendanceStatsResponse(
            away_trip_count=len(away_games),
            away_win_count=sum(
                1
                for item in away_games
                if item.result
                == AttendanceLogGameResult.WIN
            ),
            home_attendance_count=len(home_games),
            home_win_rate=self._calculate_win_rate(
                [item.result for item in home_games]
            ),
            away_win_rate=self._calculate_win_rate(
                [item.result for item in away_games]
            ),
            recent_10_attendance_count=len(
                recent_games
            ),
            recent_10_win_rate=(
                self._calculate_win_rate(
                    [
                        item.result
                        for item in recent_games
                    ]
                )
            ),
            weekday_stats=self._build_weekday_stats(
                attendance_games
            ),
        )

    def _build_weekday_stats(
        self,
        games: list[_AttendanceGame],
    ) -> list[AttendanceWeekdayStatsResponse]:
        result: list[
            AttendanceWeekdayStatsResponse
        ] = []

        for weekday_index, weekday in enumerate(
            self.WEEKDAYS
        ):
            weekday_games = [
                item
                for item in games
                if item.game_start_at.weekday()
                == weekday_index
            ]

            results = [
                item.result
                for item in weekday_games
            ]

            result.append(
                AttendanceWeekdayStatsResponse(
                    weekday=weekday,
                    attendance_count=len(
                        weekday_games
                    ),
                    win_count=self._count_result(
                        results,
                        AttendanceLogGameResult.WIN,
                    ),
                    loss_count=self._count_result(
                        results,
                        AttendanceLogGameResult.LOSS,
                    ),
                    draw_count=self._count_result(
                        results,
                        AttendanceLogGameResult.DRAW,
                    ),
                    win_rate=(
                        self._calculate_win_rate(
                            results
                        )
                    ),
                )
            )

        return result

    @staticmethod
    def _count_result(
        results: list[
            AttendanceLogGameResult | None
        ],
        target: AttendanceLogGameResult,
    ) -> int:
        return sum(
            1
            for result in results
            if result == target
        )

    @staticmethod
    def _calculate_win_rate(
        results: list[
            AttendanceLogGameResult | None
        ],
    ) -> float | None:
        decided = [
            result
            for result in results
            if result is not None
        ]

        if not decided:
            return None

        wins = sum(
            1
            for result in decided
            if result
            == AttendanceLogGameResult.WIN
        )

        return round(
            wins / len(decided) * 100,
            2,
        )

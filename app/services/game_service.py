from datetime import date
from zoneinfo import ZoneInfo

from fastapi import status

from app.core.exceptions import AppException
from app.repositories.game_repository import GameRepository
from app.repositories.stadium_repository import StadiumRepository
from app.repositories.team_repository import TeamRepository
from app.services.team_service import resolve_team_logo_url
from app.schemas.game import (
    GameRecord,
    GameResponse,
    GameStatus,
    GameTeamSummaryResponse,
)
from app.schemas.stadium import (
    StadiumResponse,
    StadiumSummaryResponse,
)
from app.schemas.team import TeamResponse


KOREA_TIMEZONE = ZoneInfo("Asia/Seoul")


class GameService:
    """경기 조회 및 필터링 비즈니스 로직을 담당합니다."""

    def __init__(
        self,
        game_repository: GameRepository | None = None,
        team_repository: TeamRepository | None = None,
        stadium_repository: StadiumRepository | None = None,
    ) -> None:
        self._game_repository = (
            game_repository
            or GameRepository()
        )
        self._team_repository = (
            team_repository
            or TeamRepository()
        )
        self._stadium_repository = (
            stadium_repository
            or StadiumRepository()
        )

    def get_games(
        self,
        *,
        game_date: date | None = None,
        team_id: str | None = None,
        stadium_id: str | None = None,
        game_status: GameStatus | None = None,
    ) -> list[GameResponse]:
        """조건에 맞는 경기 목록을 반환합니다."""

        games = self._game_repository.get_all()

        filtered_games = [
            game
            for game in games
            if self._matches_filters(
                game,
                game_date=game_date,
                team_id=team_id,
                stadium_id=stadium_id,
                game_status=game_status,
            )
        ]

        return [
            self._build_game_response(game)
            for game in filtered_games
        ]

    def get_game(self, game_id: str) -> GameResponse:
        """경기 ID로 경기 상세정보를 조회합니다."""

        game = self._game_repository.get_by_id(game_id)

        if game is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="GAME_NOT_FOUND",
                message="경기 정보를 찾을 수 없습니다.",
            )

        return self._build_game_response(game)

    @staticmethod
    def _matches_filters(
        game: GameRecord,
        *,
        game_date: date | None,
        team_id: str | None,
        stadium_id: str | None,
        game_status: GameStatus | None,
    ) -> bool:
        if game_date is not None:
            korea_game_date = (
                game.game_start_at
                .astimezone(KOREA_TIMEZONE)
                .date()
            )

            if korea_game_date != game_date:
                return False

        if team_id is not None:
            if team_id not in {
                game.home_team_id,
                game.away_team_id,
            }:
                return False

        if stadium_id is not None:
            if game.stadium_id != stadium_id:
                return False

        if game_status is not None:
            if game.status != game_status:
                return False

        return True

    def _build_game_response(
        self,
        game: GameRecord,
    ) -> GameResponse:
        home_team = self._get_team_or_raise(
            game.home_team_id
        )
        away_team = self._get_team_or_raise(
            game.away_team_id
        )
        stadium = self._get_stadium_or_raise(
            game.stadium_id
        )

        return GameResponse(
            game_id=game.game_id,
            game_start_at=game.game_start_at,
            status=game.status,
            home_team=GameTeamSummaryResponse(
                team_id=home_team.team_id,
                name=home_team.name,
                logo_url=resolve_team_logo_url(home_team),
            ),
            away_team=GameTeamSummaryResponse(
                team_id=away_team.team_id,
                name=away_team.name,
                logo_url=resolve_team_logo_url(away_team),
            ),
            stadium=StadiumSummaryResponse(
                stadium_id=stadium.stadium_id,
                name=stadium.name,
                address=stadium.address,
                latitude=stadium.latitude,
                longitude=stadium.longitude,
            ),
            home_score=game.home_score,
            away_score=game.away_score,
            result_text=game.result_text,
        )

    def _get_team_or_raise(
        self,
        team_id: str,
    ) -> TeamResponse:
        team = self._team_repository.get_by_id(team_id)

        if team is None:
            raise AppException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="INTERNAL_SERVER_ERROR",
                message="경기의 구단 정보가 올바르지 않습니다.",
            )

        return team

    def _get_stadium_or_raise(
        self,
        stadium_id: str,
    ) -> StadiumResponse:
        stadium = self._stadium_repository.get_by_id(
            stadium_id
        )

        if stadium is None:
            raise AppException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                code="INTERNAL_SERVER_ERROR",
                message="경기의 구장 정보가 올바르지 않습니다.",
            )

        return stadium

from datetime import date, datetime, timezone

import pytest

from app.core.exceptions import AppException
from app.schemas.game import (
    GameRecord,
    GameStatus,
)
from app.schemas.stadium import StadiumResponse
from app.schemas.team import TeamResponse
from app.services.game_service import GameService


class StubGameRepository:
    def __init__(
        self,
        games: list[GameRecord],
    ) -> None:
        self._games = games

    def get_all(self) -> list[GameRecord]:
        return list(self._games)

    def get_by_id(
        self,
        game_id: str,
    ) -> GameRecord | None:
        return next(
            (
                game
                for game in self._games
                if game.game_id == game_id
            ),
            None,
        )


class StubTeamRepository:
    def __init__(
        self,
        teams: list[TeamResponse],
    ) -> None:
        self._teams = {
            team.team_id: team
            for team in teams
        }

    def get_by_id(
        self,
        team_id: str,
    ) -> TeamResponse | None:
        return self._teams.get(team_id)


class StubStadiumRepository:
    def __init__(
        self,
        stadiums: list[StadiumResponse],
    ) -> None:
        self._stadiums = {
            stadium.stadium_id: stadium
            for stadium in stadiums
        }

    def get_by_id(
        self,
        stadium_id: str,
    ) -> StadiumResponse | None:
        return self._stadiums.get(stadium_id)


def create_teams() -> list[TeamResponse]:
    return [
        TeamResponse(
            team_id="lotte",
            name="롯데 자이언츠",
            short_name="롯데",
            logo_url="https://example.com/lotte.png",
            home_region="부산",
            stadium_id="sajik",
        ),
        TeamResponse(
            team_id="doosan",
            name="두산 베어스",
            short_name="두산",
            logo_url="https://example.com/doosan.png",
            home_region="서울",
            stadium_id="jamsil",
        ),
        TeamResponse(
            team_id="nc",
            name="NC 다이노스",
            short_name="NC",
            logo_url="https://example.com/nc.png",
            home_region="창원",
            stadium_id="changwon",
        ),
    ]


def create_stadiums() -> list[StadiumResponse]:
    now = datetime.now(timezone.utc)

    return [
        StadiumResponse(
            stadium_id="sajik",
            name="사직야구장",
            address="부산광역시 동래구 사직로 45",
            latitude=35.194,
            longitude=129.0615,
            region="부산",
            created_at=now,
            updated_at=now,
        ),
        StadiumResponse(
            stadium_id="changwon",
            name="창원NC파크",
            address="경상남도 창원시 마산회원구",
            latitude=35.2225,
            longitude=128.5822,
            region="경남",
            created_at=now,
            updated_at=now,
        ),
    ]


def create_games() -> list[GameRecord]:
    now = datetime.now(timezone.utc)

    return [
        GameRecord(
            game_id="game_20260815_lotte_doosan",
            home_team_id="lotte",
            away_team_id="doosan",
            stadium_id="sajik",
            game_start_at=datetime(
                2026,
                8,
                15,
                9,
                30,
                tzinfo=timezone.utc,
            ),
            status=GameStatus.SCHEDULED,
            home_score=None,
            away_score=None,
            result_text=None,
            created_at=now,
            updated_at=now,
        ),
        GameRecord(
            game_id="game_20260816_nc_doosan",
            home_team_id="nc",
            away_team_id="doosan",
            stadium_id="changwon",
            game_start_at=datetime(
                2026,
                8,
                16,
                8,
                0,
                tzinfo=timezone.utc,
            ),
            status=GameStatus.COMPLETED,
            home_score=3,
            away_score=5,
            result_text="두산 베어스 승",
            created_at=now,
            updated_at=now,
        ),
    ]


def create_service() -> GameService:
    return GameService(
        game_repository=StubGameRepository(
            create_games()
        ),
        team_repository=StubTeamRepository(
            create_teams()
        ),
        stadium_repository=StubStadiumRepository(
            create_stadiums()
        ),
    )


def test_get_games_returns_joined_response() -> None:
    service = create_service()

    games = service.get_games()

    assert len(games) == 2
    assert games[0].home_team.name == "롯데 자이언츠"
    assert games[0].away_team.name == "두산 베어스"
    assert games[0].stadium.name == "사직야구장"


def test_get_games_filters_by_korea_date() -> None:
    service = create_service()

    games = service.get_games(
        game_date=date(2026, 8, 15),
    )

    assert len(games) == 1
    assert (
        games[0].game_id
        == "game_20260815_lotte_doosan"
    )


def test_get_games_filters_by_home_or_away_team() -> None:
    service = create_service()

    games = service.get_games(
        team_id="doosan",
    )

    assert len(games) == 2


def test_get_games_filters_by_stadium() -> None:
    service = create_service()

    games = service.get_games(
        stadium_id="changwon",
    )

    assert len(games) == 1
    assert games[0].stadium.stadium_id == "changwon"


def test_get_games_filters_by_status() -> None:
    service = create_service()

    games = service.get_games(
        game_status=GameStatus.COMPLETED,
    )

    assert len(games) == 1
    assert games[0].status == GameStatus.COMPLETED
    assert games[0].home_score == 3
    assert games[0].away_score == 5


def test_get_game_returns_detail() -> None:
    service = create_service()

    game = service.get_game(
        "game_20260816_nc_doosan"
    )

    assert game.home_team.team_id == "nc"
    assert game.away_team.team_id == "doosan"
    assert game.result_text == "두산 베어스 승"


def test_get_missing_game_raises_game_not_found() -> None:
    service = create_service()

    with pytest.raises(AppException) as exception_info:
        service.get_game("missing")

    exception = exception_info.value

    assert exception.status_code == 404
    assert exception.code == "GAME_NOT_FOUND"

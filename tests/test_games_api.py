from datetime import date, datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.game import (
    GameResponse,
    GameStatus,
    GameTeamSummaryResponse,
)
from app.schemas.stadium import StadiumSummaryResponse


client = TestClient(app)


def create_game_response() -> GameResponse:
    return GameResponse(
        game_id="game_20260815_lotte_doosan",
        game_start_at=datetime(
            2026,
            8,
            15,
            9,
            30,
            tzinfo=timezone.utc,
        ),
        status=GameStatus.SCHEDULED,
        home_team=GameTeamSummaryResponse(
            team_id="lotte",
            name="롯데 자이언츠",
            logo_url="https://example.com/lotte.png",
        ),
        away_team=GameTeamSummaryResponse(
            team_id="doosan",
            name="두산 베어스",
            logo_url="https://example.com/doosan.png",
        ),
        stadium=StadiumSummaryResponse(
            stadium_id="sajik",
            name="사직야구장",
            address="부산광역시 동래구 사직로 45",
            latitude=35.194,
            longitude=129.0615,
        ),
        home_score=None,
        away_score=None,
        result_text=None,
    )


def test_get_games_returns_list_response() -> None:
    game = create_game_response()

    with patch(
        "app.api.v1.endpoints.games.GameService.get_games",
        return_value=[game],
    ):
        response = client.get("/api/v1/games")

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert body["meta"] == {
        "count": 1,
        "nextPageToken": None,
    }
    assert len(body["data"]) == 1

    returned_game = body["data"][0]

    assert (
        returned_game["gameId"]
        == "game_20260815_lotte_doosan"
    )
    assert returned_game["status"] == "SCHEDULED"
    assert returned_game["homeTeam"]["teamId"] == "lotte"
    assert returned_game["awayTeam"]["teamId"] == "doosan"
    assert returned_game["stadium"]["stadiumId"] == "sajik"


def test_get_games_forwards_query_filters() -> None:
    with patch(
        "app.api.v1.endpoints.games.GameService.get_games",
        return_value=[],
    ) as get_games:
        response = client.get(
            "/api/v1/games",
            params={
                "date": "2026-08-15",
                "teamId": "doosan",
                "stadiumId": "sajik",
                "status": "SCHEDULED",
            },
        )

    assert response.status_code == 200

    get_games.assert_called_once_with(
        game_date=date(2026, 8, 15),
        team_id="doosan",
        stadium_id="sajik",
        game_status=GameStatus.SCHEDULED,
    )

    assert response.json() == {
        "success": True,
        "data": [],
        "meta": {
            "count": 0,
            "nextPageToken": None,
        },
    }


def test_get_game_returns_detail_response() -> None:
    game = create_game_response()

    with patch(
        "app.api.v1.endpoints.games.GameService.get_game",
        return_value=game,
    ) as get_game:
        response = client.get(
            "/api/v1/games/game_20260815_lotte_doosan"
        )

    assert response.status_code == 200

    get_game.assert_called_once_with(
        "game_20260815_lotte_doosan"
    )

    body = response.json()

    assert body["success"] is True
    assert (
        body["data"]["gameId"]
        == "game_20260815_lotte_doosan"
    )
    assert body["data"]["homeTeam"]["name"] == "롯데 자이언츠"
    assert body["data"]["stadium"]["name"] == "사직야구장"


def test_get_games_rejects_invalid_status() -> None:
    response = client.get(
        "/api/v1/games",
        params={
            "status": "FINISHED",
        },
    )

    assert response.status_code == 422

    body = response.json()

    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.team import TeamResponse


client = TestClient(app)


def test_get_teams_returns_team_list() -> None:
    teams = [
        TeamResponse(
            team_id="doosan",
            name="두산 베어스",
            short_name="두산",
            logo_url="https://example.com/teams/doosan.png",
            home_region="서울",
            stadium_id="jamsil",
        ),
        TeamResponse(
            team_id="lotte",
            name="롯데 자이언츠",
            short_name="롯데",
            logo_url="https://example.com/teams/lotte.png",
            home_region="부산",
            stadium_id="sajik",
        ),
    ]

    with patch(
        "app.api.v1.endpoints.teams.TeamService.get_teams",
        return_value=teams,
    ):
        response = client.get("/api/v1/teams")

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert body["meta"]["count"] == 2
    assert body["meta"]["nextPageToken"] is None
    assert len(body["data"]) == 2

    assert body["data"][0] == {
        "name": "두산 베어스",
        "shortName": "두산",
        "logoUrl": "https://example.com/teams/doosan.png",
        "homeRegion": "서울",
        "stadiumId": "jamsil",
        "teamId": "doosan",
    }


def test_get_teams_returns_empty_list() -> None:
    with patch(
        "app.api.v1.endpoints.teams.TeamService.get_teams",
        return_value=[],
    ):
        response = client.get("/api/v1/teams")

    assert response.status_code == 200

    body = response.json()

    assert body == {
        "success": True,
        "data": [],
        "meta": {
            "count": 0,
            "nextPageToken": None,
        },
    }

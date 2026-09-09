from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.api.v1.endpoints.trip_shares as endpoint
from app.api.dependencies.auth import get_current_active_user_id
from app.main import app
from app.schemas.game import (
    GameResponse,
    GameStatus,
    GameTeamSummaryResponse,
)
from app.schemas.stadium import StadiumSummaryResponse
from app.schemas.trip_share import (
    SharedItineraryPlan,
    SharedTripResponse,
)


USER_ID = "owner_001"
TRIP_ID = "trip_001"
TOKEN = "a" * 43
NOW = datetime(2026, 8, 15, 9, 0, tzinfo=timezone.utc)


def make_shared_trip():
    return SharedTripResponse(
        title="부산 원정",
        subtitle="2026.08.15",
        trip_start_at=NOW,
        trip_end_at=NOW,
        game=GameResponse(
            game_id="game_001",
            game_start_at=NOW,
            status=GameStatus.SCHEDULED,
            home_team=GameTeamSummaryResponse(
                team_id="lotte",
                name="롯데 자이언츠",
                logo_url=None,
            ),
            away_team=GameTeamSummaryResponse(
                team_id="doosan",
                name="두산 베어스",
                logo_url=None,
            ),
            stadium=StadiumSummaryResponse(
                stadium_id="sajik",
                name="사직야구장",
                address="부산광역시 동래구 사직로 45",
                latitude=35.194,
                longitude=129.0615,
            ),
        ),
        accommodation=None,
        plan=SharedItineraryPlan(),
    )


def test_issue_share_requires_authenticated_user(monkeypatch):
    fake = SimpleNamespace(
        issue=lambda **kwargs: TOKEN,
    )
    monkeypatch.setattr(
        endpoint,
        "TripShareService",
        lambda: fake,
    )

    app.dependency_overrides[get_current_active_user_id] = (
        lambda: USER_ID
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/trips/{TRIP_ID}/share"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()

    assert body["success"] is True
    assert body["data"]["shareToken"] == TOKEN


def test_revoke_share(monkeypatch):
    fake = SimpleNamespace(
        revoke=lambda **kwargs: True,
    )
    monkeypatch.setattr(
        endpoint,
        "TripShareService",
        lambda: fake,
    )

    app.dependency_overrides[get_current_active_user_id] = (
        lambda: USER_ID
    )

    try:
        with TestClient(app) as client:
            response = client.delete(
                f"/api/v1/trips/{TRIP_ID}/share"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["data"] == {
        "revoked": True,
    }


def test_public_share_does_not_require_auth(monkeypatch):
    fake = SimpleNamespace(
        get_public_trip=lambda **kwargs: make_shared_trip(),
    )
    monkeypatch.setattr(
        endpoint,
        "TripShareService",
        lambda: fake,
    )

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/shared-trips/{TOKEN}"
        )

    assert response.status_code == 200
    assert response.json()["data"]["title"] == "부산 원정"
    assert response.headers["cache-control"] == "no-store"


def test_share_routes_are_registered():
    paths = app.openapi()["paths"]

    assert "/api/v1/trips/{tripId}/share" in paths
    assert "/api/v1/shared-trips/{shareToken}" in paths
    assert "post" in paths["/api/v1/trips/{tripId}/share"]
    assert "delete" in paths["/api/v1/trips/{tripId}/share"]
    assert "get" in paths["/api/v1/shared-trips/{shareToken}"]

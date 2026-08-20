from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import (
    ActiveUserContext,
    AuthenticatedUser,
    get_current_active_user_context,
    get_current_user,
    get_current_user_id,
)
from app.main import app
from app.schemas.team import SupportTeamResponse
from app.schemas.user import UserDocument, UserResponse


FIXED_TIME = datetime(
    2026,
    7,
    30,
    12,
    0,
    tzinfo=timezone.utc,
)


def make_user_document() -> UserDocument:
    return UserDocument(
        email="fan@example.com",
        nickname="테스트사용자",
        birth_year=2002,
        support_team_id="doosan",
        profile_image_url=None,
        onboarding_completed=True,
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
        deleted_at=None,
    )


def make_user_response(
    *,
    team_id: str = "doosan",
    team_name: str = "두산 베어스",
) -> UserResponse:
    return UserResponse(
        user_id="firebase-user-123",
        email="fan@example.com",
        nickname="테스트사용자",
        birth_year=2002,
        profile_image_url=None,
        support_team=SupportTeamResponse(
            team_id=team_id,
            name=team_name,
            logo_url=f"https://example.com/teams/{team_id}.png",
        ),
        onboarding_completed=True,
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
    )


@pytest.fixture
def authenticated_client() -> TestClient:
    app.dependency_overrides[get_current_user] = lambda: AuthenticatedUser(
        uid="firebase-user-123",
        email="fan@example.com",
    )
    app.dependency_overrides[get_current_user_id] = (
        lambda: "firebase-user-123"
    )
    app.dependency_overrides[
        get_current_active_user_context
    ] = lambda: ActiveUserContext(
        user_id="firebase-user-123",
        user=make_user_document(),
    )

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_bootstrap_user_returns_created_profile(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.bootstrap_user.return_value = make_user_response()

    with patch(
        "app.api.v1.endpoints.users.UserService",
        return_value=service,
    ):
        response = authenticated_client.post(
            "/api/v1/users/me/bootstrap",
            json={
                "nickname": "테스트사용자",
                "birthYear": 2002,
                "supportTeamId": "doosan",
            },
        )

    assert response.status_code == 201

    body = response.json()

    assert body["success"] is True
    assert body["data"]["userId"] == "firebase-user-123"
    assert body["data"]["nickname"] == "테스트사용자"
    assert body["data"]["birthYear"] == 2002
    assert body["data"]["supportTeam"]["teamId"] == "doosan"
    assert body["data"]["onboardingCompleted"] is True

    service.bootstrap_user.assert_called_once()

    arguments = service.bootstrap_user.call_args.kwargs

    assert arguments["authenticated_user"].uid == "firebase-user-123"
    assert arguments["authenticated_user"].email == "fan@example.com"
    assert arguments["request"].nickname == "테스트사용자"
    assert arguments["request"].birth_year == 2002
    assert arguments["request"].support_team_id == "doosan"


def test_get_my_profile_returns_authenticated_user(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.get_user.return_value = make_user_response()

    with patch(
        "app.api.v1.endpoints.users.UserService",
        return_value=service,
    ):
        response = authenticated_client.get(
            "/api/v1/users/me",
        )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert body["data"]["userId"] == "firebase-user-123"
    assert body["data"]["email"] == "fan@example.com"
    assert body["data"]["supportTeam"]["teamId"] == "doosan"

    service.get_user.assert_called_once()

    arguments = service.get_user.call_args

    assert arguments.args[0] == "firebase-user-123"
    assert arguments.kwargs["user"].email == "fan@example.com"


def test_update_my_support_team_returns_updated_profile(
    authenticated_client: TestClient,
) -> None:
    service = Mock()
    service.update_support_team.return_value = make_user_response(
        team_id="lotte",
        team_name="롯데 자이언츠",
    )

    with patch(
        "app.api.v1.endpoints.users.UserService",
        return_value=service,
    ):
        response = authenticated_client.patch(
            "/api/v1/users/me/support-team",
            json={
                "supportTeamId": "lotte",
            },
        )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert body["data"]["supportTeam"]["teamId"] == "lotte"
    assert body["data"]["supportTeam"]["name"] == "롯데 자이언츠"

    service.update_support_team.assert_called_once()

    arguments = service.update_support_team.call_args.kwargs

    assert arguments["user_id"] == "firebase-user-123"
    assert arguments["support_team_id"] == "lotte"
    assert arguments["user"].email == "fan@example.com"


def test_bootstrap_user_requires_birth_year(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.post(
        "/api/v1/users/me/bootstrap",
        json={
            "nickname": "테스트사용자",
            "supportTeamId": "doosan",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"

from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import (
    AuthenticatedUser,
    get_current_user,
)
from app.main import app
from app.repositories.team_repository import TeamRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import (
    UserBootstrapRequest,
    UserDocument,
    UserResponse,
)
from app.services.user_service import UserService


FIXED_TIME = datetime(
    2026,
    9,
    12,
    10,
    0,
    tzinfo=timezone.utc,
)


def make_user_without_support_team() -> UserDocument:
    return UserDocument(
        email="fan@example.com",
        nickname="테스트사용자",
        birth_year=2002,
        support_team_id=None,
        profile_image_url=None,
        onboarding_completed=True,
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
    )


def make_response_without_support_team() -> UserResponse:
    return UserResponse(
        user_id="firebase-user-123",
        email="fan@example.com",
        nickname="테스트사용자",
        birth_year=2002,
        support_team=None,
        onboarding_completed=True,
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
    )


def test_bootstrap_request_allows_omitted_support_team() -> None:
    request = UserBootstrapRequest(
        nickname="테스트사용자",
        birth_year=2002,
    )

    assert request.support_team_id is None


def test_bootstrap_request_allows_null_support_team() -> None:
    request = UserBootstrapRequest(
        nickname="테스트사용자",
        birth_year=2002,
        support_team_id=None,
    )

    assert request.support_team_id is None


def test_user_document_serializes_null_support_team() -> None:
    user = make_user_without_support_team()

    payload = user.model_dump(
        by_alias=True,
        exclude_none=False,
    )

    assert "supportTeamId" in payload
    assert payload["supportTeamId"] is None


def test_bootstrap_user_creates_profile_without_support_team() -> None:
    user_repository = Mock(spec=UserRepository)
    team_repository = Mock(spec=TeamRepository)
    favorite_collection_service = Mock()

    user_repository.exists.return_value = False
    user_repository.create.return_value = True

    service = UserService(
        user_repository=user_repository,
        team_repository=team_repository,
        favorite_collection_service=favorite_collection_service,
    )

    result = service.bootstrap_user(
        authenticated_user=AuthenticatedUser(
            uid="firebase-user-123",
            email="fan@example.com",
        ),
        request=UserBootstrapRequest(
            nickname="테스트사용자",
            birth_year=2002,
        ),
    )

    assert result.support_team is None

    team_repository.get_by_id.assert_not_called()
    user_repository.create.assert_called_once()

    created_user = user_repository.create.call_args.args[1]
    assert created_user.support_team_id is None

    favorite_collection_service.ensure_default_collection.assert_called_once_with(
        user_id="firebase-user-123"
    )


def test_get_user_returns_profile_without_support_team() -> None:
    user_repository = Mock(spec=UserRepository)
    team_repository = Mock(spec=TeamRepository)

    user_repository.get_by_id.return_value = (
        make_user_without_support_team()
    )

    service = UserService(
        user_repository=user_repository,
        team_repository=team_repository,
    )

    result = service.get_user("firebase-user-123")

    assert result.support_team is None
    team_repository.get_by_id.assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [
        {
            "nickname": "테스트사용자",
            "birthYear": 2002,
        },
        {
            "nickname": "테스트사용자",
            "birthYear": 2002,
            "supportTeamId": None,
        },
    ],
)
def test_bootstrap_api_allows_missing_or_null_support_team(
    payload: dict[str, object],
) -> None:
    app.dependency_overrides[get_current_user] = (
        lambda: AuthenticatedUser(
            uid="firebase-user-123",
            email="fan@example.com",
        )
    )

    service = Mock()
    service.bootstrap_user.return_value = (
        make_response_without_support_team()
    )

    try:
        with patch(
            "app.api.v1.endpoints.users.UserService",
            return_value=service,
        ):
            with TestClient(app) as client:
                response = client.post(
                    "/api/v1/users/me/bootstrap",
                    json=payload,
                )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201

    body = response.json()
    assert body["success"] is True
    assert body["data"]["supportTeam"] is None

    request = service.bootstrap_user.call_args.kwargs["request"]
    assert request.support_team_id is None


def test_bootstrap_openapi_does_not_require_support_team() -> None:
    schema = UserBootstrapRequest.model_json_schema(
        by_alias=True
    )

    assert "supportTeamId" not in schema.get("required", [])


def test_user_response_keeps_support_team_required() -> None:
    schema = UserResponse.model_json_schema(
        by_alias=True
    )

    assert "supportTeam" in schema.get("required", [])

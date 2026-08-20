from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from fastapi import status

from app.api.dependencies.auth import AuthenticatedUser
from app.core.exceptions import AppException
from app.repositories.team_repository import TeamRepository
from app.repositories.user_repository import UserRepository
from app.schemas.team import TeamResponse
from app.schemas.user import UserBootstrapRequest, UserDocument
from app.services.user_service import UserService


FIXED_TIME = datetime(
    2026,
    7,
    29,
    12,
    0,
    tzinfo=timezone.utc,
)


def make_team(
    team_id: str = "doosan",
    name: str = "두산 베어스",
) -> TeamResponse:
    return TeamResponse(
        team_id=team_id,
        name=name,
        short_name="두산",
        logo_url=f"https://example.com/teams/{team_id}.png",
        home_region="서울",
        stadium_id="jamsil",
    )


def make_user(
    support_team_id: str = "doosan",
) -> UserDocument:
    return UserDocument(
        email="fan@example.com",
        nickname="테스트사용자",
        birth_year=2002,
        support_team_id=support_team_id,
        profile_image_url=None,
        onboarding_completed=True,
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
    )


@pytest.fixture
def repositories() -> tuple[Mock, Mock]:
    user_repository = Mock(spec=UserRepository)
    team_repository = Mock(spec=TeamRepository)

    return user_repository, team_repository


def test_bootstrap_user_creates_profile(
    repositories: tuple[Mock, Mock],
) -> None:
    user_repository, team_repository = repositories

    user_repository.exists.return_value = False
    user_repository.create.return_value = True
    team_repository.get_by_id.return_value = make_team()

    service = UserService(
        user_repository=user_repository,
        team_repository=team_repository,
    )

    result = service.bootstrap_user(
        authenticated_user=AuthenticatedUser(
            uid="firebase-user-123",
            email="fan@example.com",
        ),
        request=UserBootstrapRequest(
            nickname="테스트사용자",
            birth_year=2002,
            support_team_id="doosan",
        ),
    )

    assert result.user_id == "firebase-user-123"
    assert result.email == "fan@example.com"
    assert result.nickname == "테스트사용자"
    assert result.birth_year == 2002
    assert result.support_team.team_id == "doosan"
    assert result.onboarding_completed is True

    user_repository.create.assert_called_once()

    created_user = user_repository.create.call_args.args[1]
    assert created_user.birth_year == 2002


def test_bootstrap_user_rejects_existing_user(
    repositories: tuple[Mock, Mock],
) -> None:
    user_repository, team_repository = repositories
    user_repository.exists.return_value = True

    service = UserService(
        user_repository=user_repository,
        team_repository=team_repository,
    )

    with pytest.raises(AppException) as exc_info:
        service.bootstrap_user(
            authenticated_user=AuthenticatedUser(
                uid="firebase-user-123",
                email="fan@example.com",
            ),
            request=UserBootstrapRequest(
                nickname="테스트사용자",
                birth_year=2002,
                support_team_id="doosan",
            ),
        )

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    assert exc_info.value.code == "USER_ALREADY_EXISTS"

    team_repository.get_by_id.assert_not_called()
    user_repository.create.assert_not_called()


def test_bootstrap_user_rejects_unknown_team(
    repositories: tuple[Mock, Mock],
) -> None:
    user_repository, team_repository = repositories

    user_repository.exists.return_value = False
    team_repository.get_by_id.return_value = None

    service = UserService(
        user_repository=user_repository,
        team_repository=team_repository,
    )

    with pytest.raises(AppException) as exc_info:
        service.bootstrap_user(
            authenticated_user=AuthenticatedUser(
                uid="firebase-user-123",
                email="fan@example.com",
            ),
            request=UserBootstrapRequest(
                nickname="테스트사용자",
                birth_year=2002,
                support_team_id="unknown",
            ),
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc_info.value.code == "TEAM_NOT_FOUND"

    user_repository.create.assert_not_called()


def test_get_user_returns_profile(
    repositories: tuple[Mock, Mock],
) -> None:
    user_repository, team_repository = repositories

    user_repository.get_by_id.return_value = make_user()
    team_repository.get_by_id.return_value = make_team()

    service = UserService(
        user_repository=user_repository,
        team_repository=team_repository,
    )

    result = service.get_user("firebase-user-123")

    assert result.user_id == "firebase-user-123"
    assert result.nickname == "테스트사용자"
    assert result.support_team.team_id == "doosan"

    user_repository.get_by_id.assert_called_once_with(
        "firebase-user-123"
    )


def test_get_user_rejects_missing_user(
    repositories: tuple[Mock, Mock],
) -> None:
    user_repository, team_repository = repositories

    user_repository.get_by_id.return_value = None

    service = UserService(
        user_repository=user_repository,
        team_repository=team_repository,
    )

    with pytest.raises(AppException) as exc_info:
        service.get_user("firebase-user-123")

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc_info.value.code == "USER_NOT_FOUND"

    team_repository.get_by_id.assert_not_called()


def test_update_support_team_changes_team(
    repositories: tuple[Mock, Mock],
) -> None:
    user_repository, team_repository = repositories

    user_repository.get_by_id.return_value = make_user()
    user_repository.update_fields.return_value = True
    team_repository.get_by_id.return_value = make_team(
        team_id="lotte",
        name="롯데 자이언츠",
    )

    service = UserService(
        user_repository=user_repository,
        team_repository=team_repository,
    )

    result = service.update_support_team(
        user_id="firebase-user-123",
        support_team_id="lotte",
    )

    assert result.user_id == "firebase-user-123"
    assert result.support_team.team_id == "lotte"
    assert result.support_team.name == "롯데 자이언츠"

    user_repository.update_fields.assert_called_once()
    update_arguments = user_repository.update_fields.call_args.args

    assert update_arguments[0] == "firebase-user-123"
    assert update_arguments[1]["supportTeamId"] == "lotte"
    assert "updatedAt" in update_arguments[1]


def test_get_user_reuses_supplied_user_without_repository_read(
    repositories: tuple[Mock, Mock],
) -> None:
    user_repository, team_repository = repositories

    user = make_user()

    team_repository.get_by_id.return_value = make_team()

    service = UserService(
        user_repository=user_repository,
        team_repository=team_repository,
    )

    result = service.get_user(
        "firebase-user-123",
        user=user,
    )

    assert result.user_id == "firebase-user-123"
    assert result.nickname == "테스트사용자"

    user_repository.get_by_id.assert_not_called()


def test_update_support_team_reuses_supplied_user_without_repository_read(
    repositories: tuple[Mock, Mock],
) -> None:
    user_repository, team_repository = repositories

    user = make_user()

    user_repository.update_fields.return_value = True
    team_repository.get_by_id.return_value = make_team(
        team_id="lotte",
        name="롯데 자이언츠",
    )

    service = UserService(
        user_repository=user_repository,
        team_repository=team_repository,
    )

    result = service.update_support_team(
        user_id="firebase-user-123",
        support_team_id="lotte",
        user=user,
    )

    assert result.support_team.team_id == "lotte"

    user_repository.get_by_id.assert_not_called()
    user_repository.update_fields.assert_called_once()

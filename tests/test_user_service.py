from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from fastapi import status

from app.api.dependencies.auth import AuthenticatedUser
from app.core.exceptions import AppException
from app.repositories.team_repository import TeamRepository
from app.repositories.user_repository import UserRepository
from app.schemas.team import TeamResponse
from app.schemas.user import (
    UserBootstrapRequest,
    UserDocument,
    UserUpdateRequest,
)
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


def test_update_user_changes_nickname_and_support_team(
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

    result = service.update_user(
        user_id="firebase-user-123",
        request=UserUpdateRequest(
            nickname="새닉네임",
            support_team_id="lotte",
        ),
    )

    assert result.nickname == "새닉네임"
    assert result.support_team.team_id == "lotte"

    user_repository.update_fields.assert_called_once()

    update_arguments = (
        user_repository.update_fields.call_args.args
    )

    assert update_arguments[0] == "firebase-user-123"
    assert update_arguments[1]["nickname"] == "새닉네임"
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


def test_update_user_reuses_supplied_user_without_repository_read(
    repositories: tuple[Mock, Mock],
) -> None:
    user_repository, team_repository = repositories

    user = make_user()
    user_repository.update_fields.return_value = True
    team_repository.get_by_id.return_value = make_team()

    service = UserService(
        user_repository=user_repository,
        team_repository=team_repository,
    )

    result = service.update_user(
        user_id="firebase-user-123",
        request=UserUpdateRequest(
            nickname="새닉네임",
        ),
        user=user,
    )

    assert result.nickname == "새닉네임"
    assert result.support_team.team_id == "doosan"

    user_repository.get_by_id.assert_not_called()
    user_repository.update_fields.assert_called_once()

    fields = user_repository.update_fields.call_args.args[1]

    assert fields["nickname"] == "새닉네임"
    assert "supportTeamId" not in fields


def test_update_user_changes_extended_profile_fields(
    repositories: tuple[Mock, Mock],
) -> None:
    user_repository, team_repository = repositories

    user = make_user()
    user_repository.get_by_id.return_value = user
    user_repository.update_fields.return_value = True
    team_repository.get_by_id.return_value = make_team()

    service = UserService(
        user_repository=user_repository,
        team_repository=team_repository,
    )

    result = service.update_user(
        user_id="firebase-user-123",
        request=UserUpdateRequest.model_validate(
            {
                "name": "서민준",
                "phoneNumber": "01012345678",
                "profileImageUrl": (
                    "https://example.com/profile.jpg"
                ),
            }
        ),
    )

    assert result.name == "서민준"
    assert result.phone_number == "01012345678"
    assert (
        result.profile_image_url
        == "https://example.com/profile.jpg"
    )

    fields = (
        user_repository.update_fields
        .call_args.args[1]
    )

    assert fields["name"] == "서민준"
    assert fields["phoneNumber"] == "01012345678"
    assert (
        fields["profileImageUrl"]
        == "https://example.com/profile.jpg"
    )


def test_update_user_can_clear_optional_profile_fields(
    repositories: tuple[Mock, Mock],
) -> None:
    user_repository, team_repository = repositories

    user = make_user().model_copy(
        update={
            "name": "기존 이름",
            "phone_number": "01012345678",
            "profile_image_url": (
                "https://example.com/old.jpg"
            ),
        }
    )

    user_repository.get_by_id.return_value = user
    user_repository.update_fields.return_value = True
    team_repository.get_by_id.return_value = make_team()

    service = UserService(
        user_repository=user_repository,
        team_repository=team_repository,
    )

    result = service.update_user(
        user_id="firebase-user-123",
        request=UserUpdateRequest.model_validate(
            {
                "name": None,
                "phoneNumber": None,
                "profileImageUrl": None,
            }
        ),
    )

    assert result.name is None
    assert result.phone_number is None
    assert result.profile_image_url is None

    fields = (
        user_repository.update_fields
        .call_args.args[1]
    )

    assert fields["name"] is None
    assert fields["phoneNumber"] is None
    assert fields["profileImageUrl"] is None


def test_get_user_generates_profile_url_from_storage_path(
    repositories: tuple[Mock, Mock],
) -> None:
    from unittest.mock import patch

    user_repository, team_repository = repositories

    user = make_user().model_copy(
        update={
            "profile_image_url": None,
            "profile_image_storage_path": (
                "users/firebase-user-123/"
                "profile/media_001.jpg"
            ),
        }
    )

    user_repository.get_by_id.return_value = user
    team_repository.get_by_id.return_value = make_team()

    storage_service = Mock()
    storage_service.create_download_url.return_value = (
        "https://storage.example/profile-read"
    )

    service = UserService(
        user_repository=user_repository,
        team_repository=team_repository,
    )

    with patch(
        "app.services.user_service.StorageService",
        return_value=storage_service,
    ):
        result = service.get_user(
            "firebase-user-123"
        )

    assert result.profile_image_url == (
        "https://storage.example/profile-read"
    )

    storage_service.create_download_url.assert_called_once_with(
        (
            "users/firebase-user-123/"
            "profile/media_001.jpg"
        )
    )


def test_update_user_changes_birth_date_and_gender(
    repositories: tuple[Mock, Mock],
) -> None:
    from datetime import date

    from app.schemas.user import UserGender

    user_repository, team_repository = repositories

    user = make_user()

    user_repository.get_by_id.return_value = user
    user_repository.update_fields.return_value = True
    team_repository.get_by_id.return_value = make_team()

    service = UserService(
        user_repository=user_repository,
        team_repository=team_repository,
    )

    result = service.update_user(
        user_id="firebase-user-123",
        request=UserUpdateRequest.model_validate(
            {
                "birthDate": "2001-09-15",
                "gender": "MALE",
            }
        ),
    )

    assert result.birth_date == date(2001, 9, 15)
    assert result.birth_year == 2001
    assert result.gender == UserGender.MALE

    fields = (
        user_repository.update_fields
        .call_args.args[1]
    )

    assert fields["birthDate"] == "2001-09-15"
    assert fields["birthYear"] == 2001
    assert fields["gender"] == "MALE"


def test_update_user_can_clear_birth_date_and_gender(
    repositories: tuple[Mock, Mock],
) -> None:
    from datetime import date

    from app.schemas.user import UserGender

    user_repository, team_repository = repositories

    user = make_user().model_copy(
        update={
            "birth_date": date(2002, 5, 17),
            "gender": UserGender.FEMALE,
        }
    )

    user_repository.get_by_id.return_value = user
    user_repository.update_fields.return_value = True
    team_repository.get_by_id.return_value = make_team()

    service = UserService(
        user_repository=user_repository,
        team_repository=team_repository,
    )

    result = service.update_user(
        user_id="firebase-user-123",
        request=UserUpdateRequest.model_validate(
            {
                "birthDate": None,
                "gender": None,
            }
        ),
    )

    assert result.birth_date is None
    assert result.gender is None

    # birthDate 삭제가 기존 가입용 birthYear까지
    # 삭제하지는 않습니다.
    assert result.birth_year == 2002

    fields = (
        user_repository.update_fields
        .call_args.args[1]
    )

    assert fields["birthDate"] is None
    assert fields["gender"] is None
    assert "birthYear" not in fields

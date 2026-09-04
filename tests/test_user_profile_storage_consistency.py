from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from app.repositories.team_repository import (
    TeamRepository,
)
from app.repositories.user_repository import (
    UserRepository,
)
from app.schemas.team import TeamRecord
from app.schemas.user import (
    UserDocument,
    UserUpdateRequest,
)
from app.services.user_service import UserService


USER_ID = "firebase-user-123"
OLD_STORAGE_PATH = (
    f"users/{USER_ID}/profile/old-profile.jpg"
)


def make_user() -> UserDocument:
    now = datetime.now(timezone.utc)

    return UserDocument(
        email="user@example.com",
        nickname="민준",
        birth_year=2002,
        name="서민준",
        phone_number="01012345678",
        support_team_id="lg",
        profile_image_url=None,
        profile_image_storage_path=(
            OLD_STORAGE_PATH
        ),
        onboarding_completed=True,
        created_at=now,
        updated_at=now,
    )


def make_team() -> TeamRecord:
    return TeamRecord(
        team_id="lg",
        name="LG 트윈스",
        short_name="LG",
        logo_url=(
            "https://legacy.example/lg.png"
        ),
        logo_storage_path=None,
        home_region="서울",
        stadium_id="jamsil",
    )


@pytest.mark.parametrize(
    "profile_image_url",
    [
        None,
        "https://example.com/new-profile.jpg",
    ],
)
def test_explicit_profile_image_url_update_clears_storage_path(
    profile_image_url: str | None,
) -> None:
    user_repository = Mock(
        spec=UserRepository
    )

    team_repository = Mock(
        spec=TeamRepository
    )

    user_repository.get_by_id.return_value = (
        make_user()
    )

    user_repository.update_fields.return_value = (
        True
    )

    team_repository.get_by_id.return_value = (
        make_team()
    )

    service = UserService(
        user_repository=user_repository,
        team_repository=team_repository,
    )

    result = service.update_user(
        user_id=USER_ID,
        request=UserUpdateRequest(
            profile_image_url=profile_image_url,
        ),
    )

    fields = (
        user_repository
        .update_fields
        .call_args.args[1]
    )

    assert (
        fields["profileImageUrl"]
        == profile_image_url
    )

    assert (
        fields["profileImageStoragePath"]
        is None
    )

    assert (
        result.profile_image_url
        == profile_image_url
    )

from datetime import date, datetime, timezone
from unittest.mock import Mock

from app.repositories.user_repository import UserRepository
from app.schemas.user import UserDocument, UserGender


FIXED_TIME = datetime(
    2026,
    9,
    20,
    1,
    0,
    tzinfo=timezone.utc,
)


def make_repository() -> tuple[
    UserRepository,
    Mock,
    Mock,
]:
    client = Mock()
    collection = Mock()
    document = Mock()

    client.collection.return_value = collection
    collection.document.return_value = document

    repository = UserRepository(client=client)

    return repository, collection, document


def test_replace_overwrites_user_document_for_rejoin() -> None:
    repository, collection, document = make_repository()

    user = UserDocument(
        email="rejoin@example.com",
        nickname="새닉네임",
        birth_year=2003,
        birth_date=None,
        gender=None,
        name="재가입 사용자",
        phone_number=None,
        support_team_id="doosan",
        profile_image_url=None,
        profile_image_storage_path=None,
        onboarding_completed=True,
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
        deleted_at=None,
    )

    repository.replace(
        "firebase-user-123",
        user,
    )

    collection.document.assert_called_once_with(
        "firebase-user-123"
    )
    document.set.assert_called_once()

    payload = document.set.call_args.args[0]

    assert payload["email"] == "rejoin@example.com"
    assert payload["nickname"] == "새닉네임"
    assert payload["birthYear"] == 2003
    assert payload["supportTeamId"] == "doosan"

    # 탈퇴 상태가 새 가입 시 해제되어야 합니다.
    assert "deletedAt" in payload
    assert payload["deletedAt"] is None

    # 탈퇴 전 프로필 이미지 정보 등이 다시 살아나면 안 됩니다.
    assert payload["profileImageUrl"] is None
    assert payload["profileImageStoragePath"] is None

    # merge=True를 사용하지 않아 기존 문서를 완전히 교체합니다.
    assert document.set.call_args.kwargs == {}


def test_replace_serializes_profile_fields() -> None:
    repository, _, document = make_repository()

    user = UserDocument(
        email="rejoin@example.com",
        nickname="새닉네임",
        birth_year=2003,
        birth_date=date(2003, 5, 17),
        gender=UserGender.MALE,
        name="재가입 사용자",
        phone_number="01012345678",
        support_team_id=None,
        profile_image_url=None,
        profile_image_storage_path=None,
        onboarding_completed=True,
        created_at=FIXED_TIME,
        updated_at=FIXED_TIME,
        deleted_at=None,
    )

    repository.replace(
        "firebase-user-123",
        user,
    )

    payload = document.set.call_args.args[0]

    assert payload["birthDate"] == "2003-05-17"
    assert payload["gender"] == "MALE"

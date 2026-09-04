from datetime import datetime, timezone

from fastapi import status

from app.api.dependencies.auth import AuthenticatedUser
from app.core.exceptions import AppException
from app.repositories.team_repository import TeamRepository
from app.repositories.user_repository import UserRepository
from app.schemas.team import SupportTeamResponse, TeamResponse
from app.services.storage_service import StorageService
from app.services.team_service import resolve_team_logo_url
from app.schemas.user import (
    UserBootstrapRequest,
    UserDocument,
    UserResponse,
    UserUpdateRequest,
)


class UserService:
    """사용자 프로필 관련 비즈니스 로직을 담당합니다."""

    def __init__(
        self,
        user_repository: UserRepository | None = None,
        team_repository: TeamRepository | None = None,
    ) -> None:
        self._user_repository = user_repository or UserRepository()
        self._team_repository = team_repository or TeamRepository()

    def bootstrap_user(
        self,
        authenticated_user: AuthenticatedUser,
        request: UserBootstrapRequest,
    ) -> UserResponse:
        """최초 사용자 프로필을 생성합니다."""

        if self._user_repository.exists(authenticated_user.uid):
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="USER_ALREADY_EXISTS",
                message="이미 생성된 사용자 프로필입니다.",
            )

        team = self._get_team_or_raise(request.support_team_id)

        if authenticated_user.email is None:
            raise AppException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code="AUTH_TOKEN_INVALID",
                message="인증 토큰에 이메일 정보가 없습니다.",
            )

        now = datetime.now(timezone.utc)

        user = UserDocument(
            email=authenticated_user.email,
            nickname=request.nickname,
            birth_year=request.birth_year,
            name=request.name,
            phone_number=request.phone_number,
            support_team_id=request.support_team_id,
            profile_image_url=None,
            onboarding_completed=True,
            created_at=now,
            updated_at=now,
        )

        created = self._user_repository.create(
            authenticated_user.uid,
            user,
        )

        if not created:
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="USER_ALREADY_EXISTS",
                message="이미 생성된 사용자 프로필입니다.",
            )

        return self._build_user_response(
            user_id=authenticated_user.uid,
            user=user,
            team=team,
        )

    def get_user(
        self,
        user_id: str,
        *,
        user: UserDocument | None = None,
    ) -> UserResponse:
        """인증된 사용자의 프로필을 조회합니다."""

        if user is None:
            user = self._user_repository.get_by_id(user_id)

        if user is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="USER_NOT_FOUND",
                message="사용자 정보를 찾을 수 없습니다.",
            )

        team = self._get_team_or_raise(user.support_team_id)

        return self._build_user_response(
            user_id=user_id,
            user=user,
            team=team,
        )

    def update_user(
        self,
        *,
        user_id: str,
        request: UserUpdateRequest,
        user: UserDocument | None = None,
    ) -> UserResponse:
        """사용자의 수정 가능한 프로필 정보를 변경합니다."""

        if user is None:
            user = self._user_repository.get_by_id(user_id)

        if user is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="USER_NOT_FOUND",
                message="사용자 정보를 찾을 수 없습니다.",
            )

        nickname = user.nickname
        name = user.name
        phone_number = user.phone_number
        profile_image_url = user.profile_image_url
        profile_image_storage_path = (
            user.profile_image_storage_path
        )
        support_team_id = user.support_team_id

        updates: dict[str, object] = {}

        if request.nickname is not None:
            nickname = request.nickname
            updates["nickname"] = request.nickname

        if "name" in request.model_fields_set:
            name = request.name
            updates["name"] = request.name

        if "phone_number" in request.model_fields_set:
            phone_number = request.phone_number
            updates["phoneNumber"] = request.phone_number

        if "profile_image_url" in request.model_fields_set:
            profile_image_url = request.profile_image_url

            # legacy profileImageUrl을 명시적으로 수정하면
            # 기존 Storage 이미지를 다시 fallback하지 않도록
            # Storage 기준 경로도 함께 해제합니다.
            profile_image_storage_path = None

            updates["profileImageUrl"] = (
                request.profile_image_url
            )
            updates["profileImageStoragePath"] = None

        if request.support_team_id is not None:
            support_team_id = request.support_team_id
            updates["supportTeamId"] = request.support_team_id

        team = self._get_team_or_raise(support_team_id)

        updated_at = datetime.now(timezone.utc)
        updates["updatedAt"] = updated_at

        updated = self._user_repository.update_fields(
            user_id,
            updates,
        )

        if not updated:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="USER_NOT_FOUND",
                message="사용자 정보를 찾을 수 없습니다.",
            )

        updated_user = user.model_copy(
            update={
                "nickname": nickname,
                "name": name,
                "phone_number": phone_number,
                "profile_image_url": profile_image_url,
                "profile_image_storage_path": (
                    profile_image_storage_path
                ),
                "support_team_id": support_team_id,
                "updated_at": updated_at,
            }
        )

        return self._build_user_response(
            user_id=user_id,
            user=updated_user,
            team=team,
        )

    def _get_team_or_raise(self, team_id: str) -> TeamResponse:
        team = self._team_repository.get_by_id(team_id)

        if team is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="TEAM_NOT_FOUND",
                message="구단 정보를 찾을 수 없습니다.",
            )

        return team

    @staticmethod
    def _build_user_response(
        *,
        user_id: str,
        user: UserDocument,
        team: TeamResponse,
    ) -> UserResponse:
        return UserResponse(
            user_id=user_id,
            email=user.email,
            nickname=user.nickname,
            birth_year=user.birth_year,
            name=user.name,
            phone_number=user.phone_number,
            profile_image_url=(
                user.profile_image_url
                if user.profile_image_url is not None
                else (
                    StorageService().create_download_url(
                        user.profile_image_storage_path
                    )
                    if user.profile_image_storage_path
                    else None
                )
            ),
            support_team=SupportTeamResponse(
                team_id=team.team_id,
                name=team.name,
                logo_url=resolve_team_logo_url(team),
            ),
            onboarding_completed=user.onboarding_completed,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

from datetime import datetime, timezone

from fastapi import status

from app.api.dependencies.auth import AuthenticatedUser
from app.core.exceptions import AppException
from app.repositories.team_repository import TeamRepository
from app.repositories.user_repository import UserRepository
from app.schemas.team import SupportTeamResponse, TeamResponse
from app.schemas.user import (
    UserBootstrapRequest,
    UserDocument,
    UserResponse,
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

    def get_user(self, user_id: str) -> UserResponse:
        """인증된 사용자의 프로필을 조회합니다."""

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

    def update_support_team(
        self,
        user_id: str,
        support_team_id: str,
    ) -> UserResponse:
        """사용자의 응원팀을 설정하거나 변경합니다."""

        user = self._user_repository.get_by_id(user_id)

        if user is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="USER_NOT_FOUND",
                message="사용자 정보를 찾을 수 없습니다.",
            )

        team = self._get_team_or_raise(support_team_id)
        updated_at = datetime.now(timezone.utc)

        updated = self._user_repository.update_fields(
            user_id,
            {
                "supportTeamId": support_team_id,
                "updatedAt": updated_at,
            },
        )

        if not updated:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="USER_NOT_FOUND",
                message="사용자 정보를 찾을 수 없습니다.",
            )

        updated_user = user.model_copy(
            update={
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
            profile_image_url=user.profile_image_url,
            support_team=SupportTeamResponse(
                team_id=team.team_id,
                name=team.name,
                logo_url=team.logo_url,
            ),
            onboarding_completed=user.onboarding_completed,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

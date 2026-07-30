from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.dependencies.auth import (
    AuthenticatedUser,
    get_current_user,
    get_current_user_id,
)
from app.schemas.response import SuccessResponse
from app.schemas.user import (
    SupportTeamUpdateRequest,
    UserBootstrapRequest,
    UserResponse,
)
from app.services.user_service import UserService


router = APIRouter(
    prefix="/users",
)


@router.post(
    "/me/bootstrap",
    response_model=SuccessResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="최초 사용자 프로필 생성",
    description="Firebase 인증 사용자의 최초 프로필을 생성합니다.",
)
def bootstrap_user(
    request: UserBootstrapRequest,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(get_current_user),
    ],
) -> SuccessResponse[UserResponse]:
    service = UserService()
    user = service.bootstrap_user(
        authenticated_user=current_user,
        request=request,
    )

    return SuccessResponse(data=user)


@router.get(
    "/me",
    response_model=SuccessResponse[UserResponse],
    summary="내 사용자 정보 조회",
    description="인증된 사용자의 프로필을 조회합니다.",
)
def get_my_profile(
    user_id: Annotated[
        str,
        Depends(get_current_user_id),
    ],
) -> SuccessResponse[UserResponse]:
    service = UserService()
    user = service.get_user(user_id)

    return SuccessResponse(data=user)


@router.patch(
    "/me/support-team",
    response_model=SuccessResponse[UserResponse],
    summary="응원팀 설정 및 변경",
    description="인증된 사용자의 응원팀을 설정하거나 변경합니다.",
)
def update_my_support_team(
    request: SupportTeamUpdateRequest,
    user_id: Annotated[
        str,
        Depends(get_current_user_id),
    ],
) -> SuccessResponse[UserResponse]:
    service = UserService()
    user = service.update_support_team(
        user_id=user_id,
        support_team_id=request.support_team_id,
    )

    return SuccessResponse(data=user)

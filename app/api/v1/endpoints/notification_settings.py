from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies.auth import (
    ActiveUserContext,
    get_current_active_user_context,
)
from app.schemas.notification import (
    NotificationConsentHistoryResponse,
    NotificationSettingsResponse,
    NotificationSettingsUpdateRequest,
)
from app.schemas.response import (
    ListMeta,
    ListSuccessResponse,
    SuccessResponse,
)
from app.services.notification_service import (
    NotificationService,
)


router = APIRouter(
    prefix="/users/me",
)


@router.get(
    "/notification-settings",
    response_model=SuccessResponse[
        NotificationSettingsResponse
    ],
    summary="내 알림 설정 조회",
    description="인증된 사용자의 현재 알림 수신 설정을 조회합니다.",
)
def get_my_notification_settings(
    active_user: Annotated[
        ActiveUserContext,
        Depends(get_current_active_user_context),
    ],
) -> SuccessResponse[NotificationSettingsResponse]:
    settings = NotificationService().get_settings(
        user_id=active_user.user_id,
    )

    return SuccessResponse(data=settings)


@router.patch(
    "/notification-settings",
    response_model=SuccessResponse[
        NotificationSettingsResponse
    ],
    summary="내 알림 설정 수정",
    description=(
        "인증된 사용자의 알림 수신 설정을 부분 수정하고 "
        "실제 변경된 항목의 이력을 저장합니다."
    ),
)
def update_my_notification_settings(
    request: NotificationSettingsUpdateRequest,
    active_user: Annotated[
        ActiveUserContext,
        Depends(get_current_active_user_context),
    ],
) -> SuccessResponse[NotificationSettingsResponse]:
    settings = NotificationService().update_settings(
        user_id=active_user.user_id,
        request=request,
    )

    return SuccessResponse(data=settings)


@router.get(
    "/notification-consent-history",
    response_model=ListSuccessResponse[
        NotificationConsentHistoryResponse
    ],
    summary="내 알림 동의 변경 이력 조회",
    description=(
        "인증된 사용자의 알림 수신 설정 변경 이력을 "
        "최신순으로 조회합니다."
    ),
)
def get_my_notification_consent_history(
    active_user: Annotated[
        ActiveUserContext,
        Depends(get_current_active_user_context),
    ],
) -> ListSuccessResponse[
    NotificationConsentHistoryResponse
]:
    histories = NotificationService().get_history(
        user_id=active_user.user_id,
    )

    return ListSuccessResponse(
        data=histories,
        meta=ListMeta(
            count=len(histories),
            next_page_token=None,
        ),
    )

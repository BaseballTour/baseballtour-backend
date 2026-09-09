from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.api.dependencies.auth import get_current_active_user_id
from app.repositories.notification_inbox_repository import (
    InvalidNotificationPageToken,
)
from app.schemas.notification_inbox import (
    NotificationResponse,
    NotificationUnreadCountResponse,
)
from app.schemas.response import (
    ListMeta,
    ListSuccessResponse,
    SuccessResponse,
)
from app.services.notification_inbox_service import (
    NotificationInboxService,
)


router = APIRouter(prefix="/notifications")


# OpenAPI 문서용 예시이며 실제 DB 데이터는 아닙니다.
NOTIFICATION_EXAMPLE = {
    "notificationId": "notification_001",
    "type": "TRIP_REMINDER",
    "title": "여행 일정 안내",
    "body": "여행 일정을 확인해 주세요.",
    "createdAt": "2026-09-09T12:00:00+09:00",
    "readAt": None,
    "targetType": "TRIP",
    "targetId": "trip_001",
    "isRead": False,
}


def _success_example(data, *, meta=None):
    value = {"success": True, "data": data}
    if meta is not None:
        value["meta"] = meta

    return {
        "content": {
            "application/json": {
                "examples": {
                    "default": {
                        "summary": "성공 응답 예시",
                        "value": value,
                    }
                }
            }
        }
    }


@router.get(
    "",
    response_model=ListSuccessResponse[NotificationResponse],
    summary="내 알림 목록 조회",
    description="인증된 사용자의 알림을 최신순으로 조회합니다.",
    responses={
        200: _success_example(
            [NOTIFICATION_EXAMPLE],
            meta={"count": 1, "nextPageToken": None},
        )
    },
)
def get_notifications(
    user_id: Annotated[str, Depends(get_current_active_user_id)],
    page_size: Annotated[
        int,
        Query(
            alias="pageSize",
            ge=1,
            le=100,
            description="한 페이지에 조회할 알림 수",
            openapi_examples={"default": {"value": 20}},
        ),
    ] = 20,
    page_token: Annotated[
        str | None,
        Query(
            alias="pageToken",
            description="이전 목록 응답의 nextPageToken",
            openapi_examples={"default": {"value": "notification_001"}},
        ),
    ] = None,
) -> ListSuccessResponse[NotificationResponse]:
    try:
        records, next_page_token = (
            NotificationInboxService().get_notifications(
                user_id=user_id,
                page_size=page_size,
                page_token=page_token,
            )
        )
    except InvalidNotificationPageToken as exc:
        raise HTTPException(
            status_code=400,
            detail="유효하지 않은 페이지 토큰입니다.",
        ) from exc

    data = [
        NotificationResponse.model_validate(record.model_dump())
        for record in records
    ]
    return ListSuccessResponse(
        data=data,
        meta=ListMeta(
            count=len(data),
            next_page_token=next_page_token,
        ),
    )


@router.get(
    "/unread-count",
    response_model=SuccessResponse[NotificationUnreadCountResponse],
    summary="내 미읽음 알림 개수 조회",
    description="인증된 사용자의 읽지 않은 알림 개수를 조회합니다.",
    responses={
        200: _success_example({"unreadCount": 3})
    },
)
def get_unread_count(
    user_id: Annotated[str, Depends(get_current_active_user_id)],
) -> SuccessResponse[NotificationUnreadCountResponse]:
    count = NotificationInboxService().get_unread_count(
        user_id=user_id
    )
    return SuccessResponse(
        data=NotificationUnreadCountResponse(unread_count=count)
    )


@router.patch(
    "/{notificationId}/read",
    response_model=SuccessResponse[NotificationResponse],
    summary="내 알림 읽음 처리",
    description="인증된 사용자의 알림을 읽음 처리합니다. 이미 읽은 알림은 기존 읽음 시간을 유지합니다.",
    responses={
        200: _success_example(
            {
                **NOTIFICATION_EXAMPLE,
                "readAt": "2026-09-09T12:05:00+09:00",
                "isRead": True,
            }
        )
    },
)
def mark_notification_read(
    notification_id: Annotated[
        str,
        Path(
            alias="notificationId",
            description="읽음 처리할 알림 ID",
            openapi_examples={"default": {"value": "notification_001"}},
        ),
    ],
    user_id: Annotated[str, Depends(get_current_active_user_id)],
) -> SuccessResponse[NotificationResponse]:
    record = NotificationInboxService().mark_read(
        user_id=user_id,
        notification_id=notification_id,
    )
    if record is None:
        raise HTTPException(
            status_code=404,
            detail="알림을 찾을 수 없습니다.",
        )

    return SuccessResponse(
        data=NotificationResponse.model_validate(record.model_dump())
    )

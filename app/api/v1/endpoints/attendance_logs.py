from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    status,
)

from app.api.dependencies.auth import (
    get_current_user_id,
)
from app.schemas.attendance_log import (
    AttendanceLogCreateRequest,
    AttendanceLogRecord,
    AttendanceLogResponse,
)
from app.schemas.response import SuccessResponse
from app.services.attendance_log_service import (
    AttendanceLogService,
)


router = APIRouter(
    prefix="/attendance-logs",
)


def to_attendance_log_response(
    log: AttendanceLogRecord,
) -> AttendanceLogResponse:
    """AttendanceLogRecord를 외부 API 응답으로 변환합니다."""

    return AttendanceLogResponse(
        attendance_log_id=log.attendance_log_id,
        trip_id=log.trip_id,
        game_id=log.game_id,
        plan_id=log.plan_id,
        log_title=log.log_title,
        summary_text=log.summary_text,
        log_status=log.log_status,
        created_at=log.created_at,
        updated_at=log.updated_at,
    )


@router.post(
    "",
    response_model=SuccessResponse[AttendanceLogResponse],
    status_code=status.HTTP_201_CREATED,
    summary="직관 로그 초안 생성",
    description=(
        "로그인 사용자의 여행과 현재 ACTIVE 일정을 기반으로 "
        "직관 로그 DRAFT와 장소별 Entry를 생성합니다."
    ),
)
def create_attendance_log(
    request: AttendanceLogCreateRequest,
    user_id: Annotated[
        str,
        Depends(get_current_user_id),
    ],
) -> SuccessResponse[AttendanceLogResponse]:
    service = AttendanceLogService()

    log = service.create_draft(
        user_id=user_id,
        trip_id=request.trip_id,
        log_title=request.log_title,
    )

    return SuccessResponse(
        data=to_attendance_log_response(log)
    )

from typing import Annotated

from fastapi import APIRouter, Depends, Path

from app.api.dependencies.auth import (
    get_current_active_user_id,
)
from app.schemas.itinerary_plan import (
    ItineraryPlanRecord,
    ItineraryPlanResponse,
)
from app.schemas.response import SuccessResponse
from app.services.attendance_log_service import (
    AttendanceLogService,
)


router = APIRouter(
    prefix="/attendance-logs",
)


def to_itinerary_plan_response(
    plan: ItineraryPlanRecord,
) -> ItineraryPlanResponse:
    """저장된 과거 일정 Plan을 API 응답으로 변환합니다."""

    return ItineraryPlanResponse(
        plan_id=plan.plan_id,
        trip_id=plan.trip_id,
        status=plan.status,
        algorithm_version=plan.algorithm_version,
        total_travel_minutes=plan.total_travel_minutes,
        total_travel_distance_meters=(
            plan.total_travel_distance_meters
        ),
        days=plan.days,
        excluded_places=plan.excluded_places,
        recommendation_summary=plan.recommendation_summary,
    )


@router.get(
    "/{attendanceLogId}/itinerary",
    response_model=SuccessResponse[
        ItineraryPlanResponse
    ],
    summary="직관 로그 일정 조회",
    description=(
        "직관 로그 생성 시점에 연결된 일정 Plan을 "
        "읽기 전용으로 조회합니다. "
        "일정이 이후 재생성되어도 당시 Plan을 반환합니다."
    ),
)
def get_attendance_log_itinerary(
    attendance_log_id: Annotated[
        str,
        Path(
            alias="attendanceLogId",
            description="직관 로그 ID",
        ),
    ],
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> SuccessResponse[ItineraryPlanResponse]:
    plan = AttendanceLogService().get_itinerary(
        user_id=user_id,
        attendance_log_id=attendance_log_id,
    )

    return SuccessResponse(
        data=to_itinerary_plan_response(plan)
    )

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Path,
    Query,
    status,
)

from app.api.dependencies.auth import (
    get_current_active_user_id,
)
from app.schemas.attendance_log import (
    AttendanceLogArchiveItemResponse,
    AttendanceLogCreateRequest,
    AttendanceLogDetailResponse,
    AttendanceLogResponse,
    AttendanceLogUpdateRequest,
    LogEntryResponse,
    LogEntryUpdateRequest,
)
from app.schemas.itinerary_plan import (
    ItineraryPlanRecord,
    ItineraryPlanResponse,
)
from app.schemas.response import (
    ListMeta,
    ListSuccessResponse,
    SuccessResponse,
)
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
        total_travel_minutes=(
            plan.total_travel_minutes
        ),
        total_travel_distance_meters=(
            plan.total_travel_distance_meters
        ),
        days=plan.days,
        excluded_places=plan.excluded_places,
        recommendation_summary=(
            plan.recommendation_summary
        ),
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=SuccessResponse[
        AttendanceLogResponse
    ],
    summary="직관 로그 초안 생성",
)
def create_attendance_log(
    request: AttendanceLogCreateRequest,
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> SuccessResponse[AttendanceLogResponse]:
    service = AttendanceLogService()

    record = service.create_draft(
        user_id=user_id,
        trip_id=request.trip_id,
        log_title=request.log_title,
    )

    return SuccessResponse(
        data=service.to_response(record)
    )


@router.get(
    "",
    response_model=ListSuccessResponse[
        AttendanceLogArchiveItemResponse
    ],
    summary="내 직관 로그 아카이브 목록 조회",
    description=(
        "직관 로그 휠 화면에 필요한 경기, 구장, "
        "승패, 대표 사진 정보를 함께 반환합니다."
    ),
)
def list_attendance_logs(
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
    page_size: Annotated[
        int,
        Query(
            alias="pageSize",
            ge=1,
            le=50,
            description="한 페이지 직관 로그 개수",
        ),
    ] = 12,
    page_token: Annotated[
        str | None,
        Query(
            alias="pageToken",
            description=(
                "이전 응답의 nextPageToken. "
                "첫 요청에서는 생략합니다."
            ),
        ),
    ] = None,
) -> ListSuccessResponse[
    AttendanceLogArchiveItemResponse
]:
    data, next_page_token = (
        AttendanceLogService().list_archive_logs(
            user_id=user_id,
            page_size=page_size,
            page_token=page_token,
        )
    )

    return ListSuccessResponse(
        data=data,
        meta=ListMeta(
            count=len(data),
            next_page_token=next_page_token,
        ),
    )


@router.get(
    "/{attendanceLogId}",
    response_model=SuccessResponse[
        AttendanceLogDetailResponse
    ],
    summary="직관 로그 상세 조회",
)
def get_attendance_log(
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
) -> SuccessResponse[
    AttendanceLogDetailResponse
]:
    data = AttendanceLogService().get_detail(
        user_id=user_id,
        attendance_log_id=attendance_log_id,
    )

    return SuccessResponse(
        data=data
    )


@router.patch(
    "/{attendanceLogId}",
    response_model=SuccessResponse[
        AttendanceLogResponse
    ],
    summary="직관 로그 수정",
)
def update_attendance_log(
    request: AttendanceLogUpdateRequest,
    attendance_log_id: Annotated[
        str,
        Path(alias="attendanceLogId"),
    ],
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> SuccessResponse[AttendanceLogResponse]:
    data = AttendanceLogService().update_log(
        user_id=user_id,
        attendance_log_id=attendance_log_id,
        request=request,
    )

    return SuccessResponse(
        data=data
    )


@router.delete(
    "/{attendanceLogId}",
    response_model=SuccessResponse[
        dict[str, bool]
    ],
    summary="직관 로그 삭제",
)
def delete_attendance_log(
    attendance_log_id: Annotated[
        str,
        Path(alias="attendanceLogId"),
    ],
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> SuccessResponse[dict[str, bool]]:
    AttendanceLogService().delete_log(
        user_id=user_id,
        attendance_log_id=attendance_log_id,
    )

    return SuccessResponse(
        data={"deleted": True}
    )


@router.patch(
    "/{attendanceLogId}/entries/{entryId}",
    response_model=SuccessResponse[
        LogEntryResponse
    ],
    summary="직관 로그 Entry 수정",
)
def update_attendance_log_entry(
    request: LogEntryUpdateRequest,
    attendance_log_id: Annotated[
        str,
        Path(alias="attendanceLogId"),
    ],
    log_entry_id: Annotated[
        str,
        Path(alias="entryId"),
    ],
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> SuccessResponse[LogEntryResponse]:
    data = AttendanceLogService().update_entry(
        user_id=user_id,
        attendance_log_id=attendance_log_id,
        log_entry_id=log_entry_id,
        request=request,
    )

    return SuccessResponse(
        data=data
    )


@router.delete(
    "/{attendanceLogId}/entries/{entryId}",
    response_model=SuccessResponse[
        dict[str, bool]
    ],
    summary="직관 로그 Entry 삭제",
)
def delete_attendance_log_entry(
    attendance_log_id: Annotated[
        str,
        Path(alias="attendanceLogId"),
    ],
    log_entry_id: Annotated[
        str,
        Path(alias="entryId"),
    ],
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> SuccessResponse[dict[str, bool]]:
    AttendanceLogService().delete_entry(
        user_id=user_id,
        attendance_log_id=attendance_log_id,
        log_entry_id=log_entry_id,
    )

    return SuccessResponse(
        data={"deleted": True}
    )


@router.delete(
    (
        "/{attendanceLogId}/entries/{entryId}"
        "/media/{mediaId}"
    ),
    response_model=SuccessResponse[
        dict[str, bool]
    ],
    summary="직관 로그 미디어 삭제",
)
def delete_attendance_log_media(
    attendance_log_id: Annotated[
        str,
        Path(alias="attendanceLogId"),
    ],
    log_entry_id: Annotated[
        str,
        Path(alias="entryId"),
    ],
    log_media_id: Annotated[
        str,
        Path(alias="mediaId"),
    ],
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> SuccessResponse[dict[str, bool]]:
    AttendanceLogService().delete_media(
        user_id=user_id,
        attendance_log_id=attendance_log_id,
        log_entry_id=log_entry_id,
        log_media_id=log_media_id,
    )

    return SuccessResponse(
        data={"deleted": True}
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

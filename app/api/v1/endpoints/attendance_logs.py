from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Path,
    Response,
    status,
)

from app.api.dependencies.auth import (
    get_current_user_id,
)
from app.schemas.attendance_log import (
    AttendanceLogCreateRequest,
    AttendanceLogDetailResponse,
    AttendanceLogRecord,
    AttendanceLogResponse,
    AttendanceLogUpdateRequest,
    LogEntryRecord,
    LogEntryResponse,
    LogEntryUpdateRequest,
    LogMediaCreateRequest,
    LogMediaRecord,
    LogMediaResponse,
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
        visibility=log.visibility,
        created_at=log.created_at,
        updated_at=log.updated_at,
    )


def to_log_media_response(
    media: LogMediaRecord,
) -> LogMediaResponse:
    """LogMediaRecord를 외부 API 응답으로 변환합니다."""

    return LogMediaResponse(
        log_media_id=media.log_media_id,
        media_type=media.media_type,
        media_url=media.media_url,
        thumbnail_url=media.thumbnail_url,
        sequence_no=media.sequence_no,
        created_at=media.created_at,
    )


def to_log_entry_response(
    entry: LogEntryRecord,
    media: list[LogMediaRecord] | None = None,
) -> LogEntryResponse:
    """LogEntryRecord를 외부 API 응답으로 변환합니다."""

    return LogEntryResponse(
        log_entry_id=entry.log_entry_id,
        plan_item_id=entry.plan_item_id,
        place_id=entry.place_id,
        sequence_no=entry.sequence_no,
        entry_type=entry.entry_type,
        entry_title=entry.entry_title,
        review_text=entry.review_text,
        rating=entry.rating,
        occurred_at=entry.occurred_at,
        media=[
            to_log_media_response(item)
            for item in (media or [])
        ],
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def to_attendance_log_detail_response(
    log: AttendanceLogRecord,
    entries: list[LogEntryRecord],
    media_by_entry_id: (
        dict[str, list[LogMediaRecord]]
        | None
    ) = None,
) -> AttendanceLogDetailResponse:
    """직관 로그와 Entry, 미디어를 상세 API 응답으로 변환합니다."""

    media_map = media_by_entry_id or {}

    return AttendanceLogDetailResponse(
        attendance_log_id=log.attendance_log_id,
        trip_id=log.trip_id,
        game_id=log.game_id,
        plan_id=log.plan_id,
        log_title=log.log_title,
        summary_text=log.summary_text,
        log_status=log.log_status,
        visibility=log.visibility,
        created_at=log.created_at,
        updated_at=log.updated_at,
        entries=[
            to_log_entry_response(
                entry,
                media_map.get(
                    entry.log_entry_id,
                    [],
                ),
            )
            for entry in entries
        ],
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


@router.get(
    "",
    response_model=ListSuccessResponse[AttendanceLogResponse],
    summary="내 직관 로그 목록 조회",
    description=(
        "로그인 사용자가 소유한 삭제되지 않은 "
        "직관 로그 목록을 조회합니다."
    ),
)
def get_my_attendance_logs(
    user_id: Annotated[
        str,
        Depends(get_current_user_id),
    ],
) -> ListSuccessResponse[AttendanceLogResponse]:
    service = AttendanceLogService()

    logs = service.get_my_logs(
        user_id=user_id,
    )

    data = [
        to_attendance_log_response(log)
        for log in logs
    ]

    return ListSuccessResponse(
        data=data,
        meta=ListMeta(
            count=len(data),
            next_page_token=None,
        ),
    )


@router.get(
    "/{attendanceLogId}",
    response_model=SuccessResponse[
        AttendanceLogDetailResponse
    ],
    summary="직관 로그 상세 조회",
    description=(
        "로그인 사용자가 소유한 직관 로그와 "
        "장소별 Entry 목록을 조회합니다."
    ),
)
def get_attendance_log_detail(
    attendance_log_id: Annotated[
        str,
        Path(
            alias="attendanceLogId",
            description="직관 로그 ID",
        ),
    ],
    user_id: Annotated[
        str,
        Depends(get_current_user_id),
    ],
) -> SuccessResponse[AttendanceLogDetailResponse]:
    service = AttendanceLogService()

    (
        log,
        entries,
        media_by_entry_id,
    ) = service.get_log_detail_with_media(
        user_id=user_id,
        attendance_log_id=attendance_log_id,
    )

    return SuccessResponse(
        data=to_attendance_log_detail_response(
            log,
            entries,
            media_by_entry_id,
        )
    )


@router.patch(
    "/{attendanceLogId}",
    response_model=SuccessResponse[
        AttendanceLogResponse
    ],
    summary="직관 로그 수정",
    description=(
        "로그인 사용자가 소유한 직관 로그의 "
        "제목, 한 줄 요약, 상태를 수정합니다."
    ),
)
def update_attendance_log(
    attendance_log_id: Annotated[
        str,
        Path(
            alias="attendanceLogId",
            description="직관 로그 ID",
        ),
    ],
    request: AttendanceLogUpdateRequest,
    user_id: Annotated[
        str,
        Depends(get_current_user_id),
    ],
) -> SuccessResponse[AttendanceLogResponse]:
    service = AttendanceLogService()

    log = service.update_log(
        user_id=user_id,
        attendance_log_id=attendance_log_id,
        request=request,
    )

    return SuccessResponse(
        data=to_attendance_log_response(log)
    )


@router.delete(
    "/{attendanceLogId}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="직관 로그 삭제",
    description=(
        "로그인 사용자가 소유한 직관 로그를 "
        "soft delete합니다."
    ),
)
def delete_attendance_log(
    attendance_log_id: Annotated[
        str,
        Path(
            alias="attendanceLogId",
            description="직관 로그 ID",
        ),
    ],
    user_id: Annotated[
        str,
        Depends(get_current_user_id),
    ],
) -> Response:
    service = AttendanceLogService()

    service.delete_log(
        user_id=user_id,
        attendance_log_id=attendance_log_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )


@router.post(
    "/{attendanceLogId}/entries/{logEntryId}/media",
    response_model=SuccessResponse[
        LogMediaResponse
    ],
    status_code=status.HTTP_201_CREATED,
    summary="직관 로그 미디어 저장",
    description=(
        "직관 로그 Entry에 사진 또는 "
        "동영상 URL 정보를 저장합니다."
    ),
)
def create_log_media(
    attendance_log_id: Annotated[
        str,
        Path(
            alias="attendanceLogId",
            description="직관 로그 ID",
        ),
    ],
    log_entry_id: Annotated[
        str,
        Path(
            alias="logEntryId",
            description="로그 Entry ID",
        ),
    ],
    request: LogMediaCreateRequest,
    user_id: Annotated[
        str,
        Depends(get_current_user_id),
    ],
) -> SuccessResponse[LogMediaResponse]:
    service = AttendanceLogService()

    media = service.create_media(
        user_id=user_id,
        attendance_log_id=attendance_log_id,
        log_entry_id=log_entry_id,
        request=request,
    )

    return SuccessResponse(
        data=to_log_media_response(media)
    )


@router.delete(
    (
        "/{attendanceLogId}/entries/"
        "{logEntryId}/media/{mediaId}"
    ),
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="직관 로그 미디어 삭제",
    description=(
        "직관 로그 Entry에 저장된 "
        "미디어 정보를 삭제합니다."
    ),
)
def delete_log_media(
    attendance_log_id: Annotated[
        str,
        Path(
            alias="attendanceLogId",
            description="직관 로그 ID",
        ),
    ],
    log_entry_id: Annotated[
        str,
        Path(
            alias="logEntryId",
            description="로그 Entry ID",
        ),
    ],
    log_media_id: Annotated[
        str,
        Path(
            alias="mediaId",
            description="로그 미디어 ID",
        ),
    ],
    user_id: Annotated[
        str,
        Depends(get_current_user_id),
    ],
) -> Response:
    service = AttendanceLogService()

    service.delete_media(
        user_id=user_id,
        attendance_log_id=attendance_log_id,
        log_entry_id=log_entry_id,
        log_media_id=log_media_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )


@router.patch(
    "/{attendanceLogId}/entries/{logEntryId}",
    response_model=SuccessResponse[
        LogEntryResponse
    ],
    summary="직관 로그 Entry 수정",
    description=(
        "직관 로그의 장소 또는 경기 Entry에 "
        "제목, 후기, 발생 시각을 저장하거나 수정합니다."
    ),
)
def update_log_entry(
    attendance_log_id: Annotated[
        str,
        Path(
            alias="attendanceLogId",
            description="직관 로그 ID",
        ),
    ],
    log_entry_id: Annotated[
        str,
        Path(
            alias="logEntryId",
            description="로그 Entry ID",
        ),
    ],
    request: LogEntryUpdateRequest,
    user_id: Annotated[
        str,
        Depends(get_current_user_id),
    ],
) -> SuccessResponse[LogEntryResponse]:
    service = AttendanceLogService()

    entry, media = service.update_entry(
        user_id=user_id,
        attendance_log_id=attendance_log_id,
        log_entry_id=log_entry_id,
        request=request,
    )

    return SuccessResponse(
        data=to_log_entry_response(
            entry,
            media,
        )
    )

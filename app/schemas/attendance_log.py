from enum import Enum

from pydantic import (
    AwareDatetime,
    ConfigDict,
    Field,
    model_validator,
)

from app.schemas.base import ApiModel


class AttendanceLogStatus(str, Enum):
    """직관 로그 상태."""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class LogEntryType(str, Enum):
    """직관 로그 타임라인 항목 종류."""

    PLACE = "PLACE"
    GAME = "GAME"
    MOVE = "MOVE"
    NOTE = "NOTE"


class LogMediaType(str, Enum):
    """직관 로그 미디어 종류."""

    IMAGE = "IMAGE"
    VIDEO = "VIDEO"


class AttendanceLogCreateRequest(ApiModel):
    """
    여행을 기반으로 직관 로그 초안을 생성하는 요청.

    gameId와 planId는 서버가 Trip을 통해 결정합니다.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "tripId": "trip_001",
                    "logTitle": "사직 원정 직관 기록",
                }
            ]
        }
    )

    trip_id: str = Field(
        min_length=1,
        description="직관 로그를 생성할 여행 ID",
    )

    log_title: str | None = Field(
        default=None,
        min_length=1,
        max_length=150,
        description=(
            "직관 로그 제목. 생략하면 서버가 "
            "여행 정보를 기반으로 생성합니다."
        ),
    )


class AttendanceLogUpdateRequest(ApiModel):
    """직관 로그 기본 정보 수정 요청."""

    log_title: str | None = Field(
        default=None,
        min_length=1,
        max_length=150,
    )

    summary_text: str | None = None

    log_status: AttendanceLogStatus | None = None

    @model_validator(mode="after")
    def validate_at_least_one_field(
        self,
    ) -> "AttendanceLogUpdateRequest":
        if not self.model_fields_set:
            raise ValueError(
                "수정할 필드를 하나 이상 전달해야 합니다."
            )

        return self


class AttendanceLogDocument(ApiModel):
    """
    Firestore attendanceLogs 문서.

    ERD의 trip_game_id는 현재 백엔드의
    tripId + gameId 조합으로 표현합니다.
    """

    user_id: str = Field(
        min_length=1,
        description="로그 소유자 Firebase UID",
    )

    trip_id: str = Field(
        min_length=1,
        description="여행 ID",
    )

    game_id: str = Field(
        min_length=1,
        description="Trip에 연결된 경기 ID",
    )

    plan_id: str | None = Field(
        default=None,
        description="로그 생성 시점의 확정 일정 ID",
    )

    log_title: str = Field(
        min_length=1,
        max_length=150,
    )

    summary_text: str | None = None

    log_status: AttendanceLogStatus = (
        AttendanceLogStatus.DRAFT
    )

    created_at: AwareDatetime
    updated_at: AwareDatetime
    deleted_at: AwareDatetime | None = None


class AttendanceLogRecord(AttendanceLogDocument):
    """Firestore에서 조회한 직관 로그."""

    attendance_log_id: str = Field(
        min_length=1,
    )


class LogMediaCreateRequest(ApiModel):
    """로그 Entry에 사진 또는 동영상을 추가하는 요청."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "mediaType": "IMAGE",
                    "mediaUrl": (
                        "https://example.com/"
                        "attendance/photo.jpg"
                    ),
                    "thumbnailUrl": None,
                    "sequenceNo": 1,
                }
            ]
        }
    )

    media_type: LogMediaType

    media_url: str = Field(
        min_length=1,
        max_length=500,
    )

    thumbnail_url: str | None = Field(
        default=None,
        max_length=500,
    )

    sequence_no: int = Field(
        ge=1,
    )


class LogMediaDocument(ApiModel):
    """
    Firestore entries/{entryId}/media 하위 문서.

    ERD의 log_entry_id FK는 부모 경로로 표현합니다.
    """

    media_type: LogMediaType

    media_url: str = Field(
        min_length=1,
        max_length=500,
    )

    thumbnail_url: str | None = Field(
        default=None,
        max_length=500,
    )

    sequence_no: int = Field(
        ge=1,
    )

    created_at: AwareDatetime


class LogMediaRecord(LogMediaDocument):
    """Firestore에서 조회한 로그 미디어."""

    log_media_id: str = Field(
        min_length=1,
    )


class LogEntryUpdateRequest(ApiModel):
    """직관 로그 타임라인 Entry 수정 요청."""

    entry_title: str | None = Field(
        default=None,
        min_length=1,
        max_length=150,
    )

    review_text: str | None = None

    occurred_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_at_least_one_field(
        self,
    ) -> "LogEntryUpdateRequest":
        if not self.model_fields_set:
            raise ValueError(
                "수정할 필드를 하나 이상 전달해야 합니다."
            )

        return self


class LogEntryDocument(ApiModel):
    """
    Firestore attendanceLogs/{logId}/entries 문서.

    ERD의 attendance_log_id FK는 부모 경로로 표현합니다.
    """

    plan_item_id: str | None = None
    place_id: str | None = None

    sequence_no: int = Field(
        ge=1,
    )

    entry_type: LogEntryType

    entry_title: str = Field(
        min_length=1,
        max_length=150,
    )

    review_text: str | None = None

    occurred_at: AwareDatetime | None = None

    created_at: AwareDatetime
    updated_at: AwareDatetime


class LogEntryRecord(LogEntryDocument):
    """Firestore에서 조회한 로그 Entry."""

    log_entry_id: str = Field(
        min_length=1,
    )


class LogMediaResponse(ApiModel):
    """로그 미디어 API 응답."""

    log_media_id: str
    media_type: LogMediaType
    media_url: str
    thumbnail_url: str | None = None
    sequence_no: int
    created_at: AwareDatetime


class LogEntryResponse(ApiModel):
    """로그 Entry API 응답."""

    log_entry_id: str
    plan_item_id: str | None = None
    place_id: str | None = None

    sequence_no: int
    entry_type: LogEntryType
    entry_title: str

    review_text: str | None = None
    occurred_at: AwareDatetime | None = None

    media: list[LogMediaResponse] = Field(
        default_factory=list,
    )

    created_at: AwareDatetime
    updated_at: AwareDatetime


class AttendanceLogResponse(ApiModel):
    """직관 로그 목록용 응답."""

    attendance_log_id: str
    trip_id: str
    game_id: str
    plan_id: str | None = None

    log_title: str
    summary_text: str | None = None
    log_status: AttendanceLogStatus

    created_at: AwareDatetime
    updated_at: AwareDatetime


class AttendanceLogDetailResponse(
    AttendanceLogResponse
):
    """직관 로그 상세 응답."""

    entries: list[LogEntryResponse] = Field(
        default_factory=list,
    )

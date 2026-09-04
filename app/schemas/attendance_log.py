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


class AttendanceLogVisibility(str, Enum):
    """직관 로그 공개 범위."""

    PRIVATE = "PRIVATE"
    PUBLIC = "PUBLIC"


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

    seat: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description=(
            "관람 좌석 정보. 예: 3루 내야 B블록 15열. "
            "null이면 삭제합니다."
        ),
    )

    log_status: AttendanceLogStatus | None = None

    visibility: AttendanceLogVisibility | None = None

    @model_validator(mode="after")
    def validate_at_least_one_field(
        self,
    ) -> "AttendanceLogUpdateRequest":
        if not self.model_fields_set:
            raise ValueError(
                "수정할 필드를 하나 이상 전달해야 합니다."
            )

        if (
            "log_title" in self.model_fields_set
            and self.log_title is None
        ):
            raise ValueError(
                "직관 로그 제목은 null로 변경할 수 없습니다."
            )

        if (
            "log_status" in self.model_fields_set
            and self.log_status is None
        ):
            raise ValueError(
                "직관 로그 상태는 null로 변경할 수 없습니다."
            )

        if (
            "visibility" in self.model_fields_set
            and self.visibility is None
        ):
            raise ValueError(
                "직관 로그 공개 범위는 null로 변경할 수 없습니다."
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

    support_team_id: str | None = Field(
        default=None,
        description=(
            "직관 로그 생성 당시 사용자의 응원팀 ID. "
            "기존 로그 호환을 위해 null을 허용합니다."
        ),
    )

    log_title: str = Field(
        min_length=1,
        max_length=150,
    )

    summary_text: str | None = None

    seat: str | None = Field(
        default=None,
        max_length=100,
        description="관람 좌석 정보",
    )

    log_status: AttendanceLogStatus = (
        AttendanceLogStatus.DRAFT
    )

    visibility: AttendanceLogVisibility = (
        AttendanceLogVisibility.PRIVATE
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

    실제 파일 위치는 storagePath로 영구 저장하고,
    mediaUrl은 응답 시 signed URL로 생성합니다.
    """

    media_type: LogMediaType

    storage_path: str | None = Field(
        default=None,
        min_length=1,
        max_length=1024,
        description=(
            "Firebase Storage 객체 경로. "
            "기존 URL 기반 데이터는 null일 수 있습니다."
        ),
    )

    content_type: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description=(
            "Storage 객체 Content-Type. "
            "기존 URL 기반 데이터는 null일 수 있습니다."
        ),
    )

    media_url: str | None = Field(
        default=None,
        max_length=2048,
        description="기존 데이터 호환용 URL",
    )

    thumbnail_url: str | None = Field(
        default=None,
        max_length=2048,
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

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "entryTitle": "경기장 입장",
                    "reviewText": "경기 시작 전에 입장했습니다.",
                    "occurredAt": "2026-08-19T17:30:00+09:00",
                }
            ]
        }
    )

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
    seat: str | None = None
    log_status: AttendanceLogStatus

    visibility: AttendanceLogVisibility
    created_at: AwareDatetime
    updated_at: AwareDatetime


class AttendanceLogHomeSide(str, Enum):
    """응원팀 기준 해당 경기의 홈/원정 구분."""

    HOME = "HOME"
    AWAY = "AWAY"
    OTHER = "OTHER"


class AttendanceLogGameResult(str, Enum):
    """응원팀 기준 직관 경기 결과."""

    WIN = "WIN"
    LOSS = "LOSS"
    DRAW = "DRAW"


class AttendanceLogArchiveItemResponse(ApiModel):
    """직관 로그 아카이브 휠 카드 응답."""

    attendance_log_id: str
    trip_id: str
    game_id: str
    plan_id: str | None = None

    log_title: str
    summary_text: str | None = None
    seat: str | None = None

    game_start_at: AwareDatetime
    stadium_name: str

    home_team_name: str
    away_team_name: str

    home_score: int | None = None
    away_score: int | None = None

    home_side: AttendanceLogHomeSide
    result: AttendanceLogGameResult | None = None

    cover_image_url: str | None = None

    log_status: AttendanceLogStatus
    visibility: AttendanceLogVisibility

    created_at: AwareDatetime
    updated_at: AwareDatetime


class AttendanceLogDetailResponse(
    AttendanceLogResponse
):
    """직관 로그 상세 응답."""

    entries: list[LogEntryResponse] = Field(
        default_factory=list,
    )

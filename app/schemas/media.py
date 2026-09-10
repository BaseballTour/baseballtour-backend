from enum import Enum

from pydantic import (
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.schemas.base import ApiModel


class MediaPurpose(str, Enum):
    """미디어 업로드 용도."""

    PROFILE_IMAGE = "PROFILE_IMAGE"
    TRIP_COVER_IMAGE = "TRIP_COVER_IMAGE"
    ATTENDANCE_LOG = "ATTENDANCE_LOG"
    ATTENDANCE_LOG_COVER_IMAGE = "ATTENDANCE_LOG_COVER_IMAGE"


class MediaUploadUrlRequest(ApiModel):
    """Firebase Storage 업로드 URL 발급 요청."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "purpose": "PROFILE_IMAGE",
                    "fileName": "profile.jpg",
                    "contentType": "image/jpeg",
                    "fileSizeBytes": 1048576,
                }
            ]
        }
    )

    purpose: MediaPurpose

    file_name: str = Field(
        min_length=1,
        max_length=255,
    )

    content_type: str = Field(
        min_length=1,
        max_length=100,
    )

    file_size_bytes: int = Field(
        gt=0,
        description="업로드할 파일 크기(bytes)",
    )

    trip_id: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="여행 커버이미지를 연결할 여행 ID",
    )

    attendance_log_id: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9_-]+$",
    )

    log_entry_id: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9_-]+$",
    )

    @field_validator(
        "file_name",
        "content_type",
    )
    @classmethod
    def normalize_text(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "빈 문자열은 사용할 수 없습니다."
            )

        return normalized

    @field_validator("content_type")
    @classmethod
    def normalize_content_type(
        cls,
        value: str,
    ) -> str:
        return value.lower()

    @model_validator(mode="after")
    def validate_target(
        self,
    ) -> "MediaUploadUrlRequest":
        if self.purpose == MediaPurpose.TRIP_COVER_IMAGE:
            if self.trip_id is None:
                raise ValueError(
                    "여행 커버이미지에는 tripId가 필요합니다."
                )
        elif self.trip_id is not None:
            raise ValueError(
                "이 용도에는 tripId를 전달할 수 없습니다."
            )

        if self.purpose == MediaPurpose.ATTENDANCE_LOG:
            if (
                self.attendance_log_id is None
                or self.log_entry_id is None
            ):
                raise ValueError(
                    "직관 로그 미디어에는 "
                    "attendanceLogId와 logEntryId가 필요합니다."
                )

        elif (
            self.purpose
            == MediaPurpose.ATTENDANCE_LOG_COVER_IMAGE
        ):
            if self.attendance_log_id is None:
                raise ValueError(
                    "직관 로그 대표이미지에는 "
                    "attendanceLogId가 필요합니다."
                )

            if self.log_entry_id is not None:
                raise ValueError(
                    "직관 로그 대표이미지에는 "
                    "logEntryId를 전달할 수 없습니다."
                )

        elif any(
            getattr(self, name) is not None
            for name in (
                "attendance_log_id",
                "log_entry_id",
            )
        ):
            raise ValueError(
                "이 용도에는 직관 로그 정보를 "
                "전달할 수 없습니다."
            )

        return self


class MediaUploadUrlResponse(ApiModel):
    """Firebase Storage 업로드 URL 응답."""

    upload_url: str
    storage_path: str
    expected_cover_image_storage_path: str | None = None
    content_type: str
    expires_in_seconds: int
    required_headers: dict[str, str]


class MediaCompleteRequest(ApiModel):
    """Storage 직접 업로드 완료 등록 요청."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "purpose": "ATTENDANCE_LOG",
                    "storagePath": (
                        "users/firebase_uid/"
                        "attendance-logs/log_001/"
                        "entry_001/media_example.jpg"
                    ),
                    "contentType": "image/jpeg",
                    "attendanceLogId": "log_001",
                    "logEntryId": "entry_001",
                    "sequenceNo": 1,
                }
            ]
        }
    )

    purpose: MediaPurpose

    storage_path: str = Field(
        min_length=1,
        max_length=1024,
    )
    expected_cover_image_storage_path: str | None = None

    content_type: str = Field(
        min_length=1,
        max_length=100,
    )

    trip_id: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="여행 커버이미지를 연결할 여행 ID",
    )

    attendance_log_id: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9_-]+$",
    )

    log_entry_id: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9_-]+$",
    )

    sequence_no: int | None = Field(
        default=None,
        ge=1,
    )

    @field_validator(
        "storage_path",
        "content_type",
    )
    @classmethod
    def normalize_text(
        cls,
        value: str,
    ) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError(
                "빈 문자열은 사용할 수 없습니다."
            )

        return normalized

    @field_validator("content_type")
    @classmethod
    def normalize_content_type(
        cls,
        value: str,
    ) -> str:
        return value.lower()

    @field_validator("storage_path")
    @classmethod
    def validate_storage_path(
        cls,
        value: str,
    ) -> str:
        if ".." in value.split("/"):
            raise ValueError(
                "올바르지 않은 Storage 경로입니다."
            )

        return value

    @model_validator(mode="after")
    def validate_target(
        self,
    ) -> "MediaCompleteRequest":
        cover_purposes = {
            MediaPurpose.TRIP_COVER_IMAGE,
            MediaPurpose.ATTENDANCE_LOG_COVER_IMAGE,
        }

        if self.purpose in cover_purposes:
            if (
                "expected_cover_image_storage_path"
                not in self.model_fields_set
            ):
                raise ValueError(
                    "커버이미지에는 "
                    "expectedCoverImageStoragePath가 필요합니다."
                )
        elif (
            "expected_cover_image_storage_path"
            in self.model_fields_set
        ):
            raise ValueError(
                "이 용도에는 "
                "expectedCoverImageStoragePath를 "
                "전달할 수 없습니다."
            )

        if self.purpose == MediaPurpose.TRIP_COVER_IMAGE:
            if self.trip_id is None:
                raise ValueError(
                    "여행 커버이미지에는 tripId가 필요합니다."
                )
        elif self.trip_id is not None:
            raise ValueError(
                "이 용도에는 tripId를 전달할 수 없습니다."
            )

        if self.purpose == MediaPurpose.ATTENDANCE_LOG:
            if (
                self.attendance_log_id is None
                or self.log_entry_id is None
                or self.sequence_no is None
            ):
                raise ValueError(
                    "직관 로그 미디어에는 대상 ID와 "
                    "순서 정보가 필요합니다."
                )

        elif (
            self.purpose
            == MediaPurpose.ATTENDANCE_LOG_COVER_IMAGE
        ):
            if self.attendance_log_id is None:
                raise ValueError(
                    "직관 로그 대표이미지에는 "
                    "attendanceLogId가 필요합니다."
                )

            if (
                self.log_entry_id is not None
                or self.sequence_no is not None
            ):
                raise ValueError(
                    "직관 로그 대표이미지에는 "
                    "logEntryId와 sequenceNo를 "
                    "전달할 수 없습니다."
                )

        elif any(
            getattr(self, name) is not None
            for name in (
                "attendance_log_id",
                "log_entry_id",
                "sequence_no",
            )
        ):
            raise ValueError(
                "이 용도에는 직관 로그 정보를 "
                "전달할 수 없습니다."
            )

        return self


class MediaCompleteResponse(ApiModel):
    """Storage 업로드 완료 등록 응답."""

    purpose: MediaPurpose
    storage_path: str
    content_type: str
    media_url: str

    log_media_id: str | None = None
    sequence_no: int | None = None

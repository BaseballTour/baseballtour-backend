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
    ATTENDANCE_LOG = "ATTENDANCE_LOG"


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
        if (
            self.purpose
            == MediaPurpose.ATTENDANCE_LOG
        ):
            if (
                self.attendance_log_id is None
                or self.log_entry_id is None
            ):
                raise ValueError(
                    "직관 로그 미디어는 attendanceLogId와 "
                    "logEntryId가 필요합니다."
                )

        if (
            self.purpose
            == MediaPurpose.PROFILE_IMAGE
            and (
                self.attendance_log_id is not None
                or self.log_entry_id is not None
            )
        ):
            raise ValueError(
                "프로필 이미지에는 직관 로그 ID를 "
                "전달할 수 없습니다."
            )

        return self


class MediaUploadUrlResponse(ApiModel):
    """Firebase Storage 업로드 URL 응답."""

    upload_url: str
    storage_path: str
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

    content_type: str = Field(
        min_length=1,
        max_length=100,
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
        if (
            self.purpose
            == MediaPurpose.ATTENDANCE_LOG
        ):
            if (
                self.attendance_log_id is None
                or self.log_entry_id is None
                or self.sequence_no is None
            ):
                raise ValueError(
                    "직관 로그 미디어 완료 요청에는 "
                    "attendanceLogId, logEntryId, "
                    "sequenceNo가 필요합니다."
                )

        if (
            self.purpose
            == MediaPurpose.PROFILE_IMAGE
            and (
                self.attendance_log_id is not None
                or self.log_entry_id is not None
                or self.sequence_no is not None
            )
        ):
            raise ValueError(
                "프로필 이미지 완료 요청에는 "
                "직관 로그 정보를 전달할 수 없습니다."
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

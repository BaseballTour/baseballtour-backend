from enum import Enum

from pydantic import (
    AwareDatetime,
    ConfigDict,
    model_validator,
)

from app.schemas.base import ApiModel


class NotificationConsentType(str, Enum):
    GAME_REMINDER = "GAME_REMINDER"
    TRIP_REMINDER = "TRIP_REMINDER"
    MARKETING = "MARKETING"


class NotificationSettingsDocument(ApiModel):
    """사용자별 알림 설정 Firestore 문서."""

    game_reminder_enabled: bool
    trip_reminder_enabled: bool
    marketing_enabled: bool
    updated_at: AwareDatetime


class NotificationSettingsResponse(ApiModel):
    """사용자 알림 설정 API 응답."""

    game_reminder_enabled: bool
    trip_reminder_enabled: bool
    marketing_enabled: bool
    updated_at: AwareDatetime


class NotificationSettingsUpdateRequest(ApiModel):
    """알림 설정 부분 수정 요청."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "gameReminderEnabled": True,
                    "tripReminderEnabled": True,
                    "marketingEnabled": False,
                }
            ]
        }
    )

    game_reminder_enabled: bool | None = None
    trip_reminder_enabled: bool | None = None
    marketing_enabled: bool | None = None

    @model_validator(mode="after")
    def validate_update_fields(
        self,
    ) -> "NotificationSettingsUpdateRequest":
        supported_fields = {
            "game_reminder_enabled",
            "trip_reminder_enabled",
            "marketing_enabled",
        }

        provided = self.model_fields_set & supported_fields

        if not provided:
            raise ValueError(
                "수정할 알림 설정을 하나 이상 입력해야 합니다."
            )

        for field_name in provided:
            if getattr(self, field_name) is None:
                raise ValueError(
                    "알림 설정은 null로 변경할 수 없습니다."
                )

        return self


class NotificationConsentHistoryDocument(ApiModel):
    """알림 수신 설정 변경 이력 Firestore 문서."""

    consent_type: NotificationConsentType
    previous_enabled: bool
    enabled: bool
    changed_at: AwareDatetime


class NotificationConsentHistoryRecord(
    NotificationConsentHistoryDocument
):
    history_id: str


class NotificationConsentHistoryResponse(ApiModel):
    """알림 수신 설정 변경 이력 API 응답."""

    history_id: str
    consent_type: NotificationConsentType
    previous_enabled: bool
    enabled: bool
    changed_at: AwareDatetime

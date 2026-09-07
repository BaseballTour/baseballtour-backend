from datetime import datetime, timezone

from app.repositories.notification_repository import (
    NotificationRepository,
)
from app.schemas.notification import (
    NotificationConsentHistoryDocument,
    NotificationConsentHistoryResponse,
    NotificationConsentType,
    NotificationSettingsDocument,
    NotificationSettingsResponse,
    NotificationSettingsUpdateRequest,
)


class NotificationService:
    """사용자 알림 설정 및 변경 이력 로직."""

    def __init__(
        self,
        repository: NotificationRepository | None = None,
    ) -> None:
        self._repository = (
            repository or NotificationRepository()
        )

    def get_settings(
        self,
        *,
        user_id: str,
    ) -> NotificationSettingsResponse:
        settings = self._repository.get_settings(user_id)

        if settings is None:
            settings = self._create_default_settings()

            self._repository.save_settings(
                user_id=user_id,
                settings=settings,
            )

        return self._to_response(settings)

    def update_settings(
        self,
        *,
        user_id: str,
        request: NotificationSettingsUpdateRequest,
    ) -> NotificationSettingsResponse:
        current = self._repository.get_settings(user_id)

        if current is None:
            current = self._create_default_settings()

        game_reminder_enabled = (
            current.game_reminder_enabled
        )
        trip_reminder_enabled = (
            current.trip_reminder_enabled
        )
        marketing_enabled = current.marketing_enabled

        now = datetime.now(timezone.utc)

        histories: list[
            NotificationConsentHistoryDocument
        ] = []

        if "game_reminder_enabled" in request.model_fields_set:
            new_value = request.game_reminder_enabled

            if (
                new_value is not None
                and new_value != game_reminder_enabled
            ):
                histories.append(
                    NotificationConsentHistoryDocument(
                        consent_type=(
                            NotificationConsentType.GAME_REMINDER
                        ),
                        previous_enabled=game_reminder_enabled,
                        enabled=new_value,
                        changed_at=now,
                    )
                )
                game_reminder_enabled = new_value

        if "trip_reminder_enabled" in request.model_fields_set:
            new_value = request.trip_reminder_enabled

            if (
                new_value is not None
                and new_value != trip_reminder_enabled
            ):
                histories.append(
                    NotificationConsentHistoryDocument(
                        consent_type=(
                            NotificationConsentType.TRIP_REMINDER
                        ),
                        previous_enabled=trip_reminder_enabled,
                        enabled=new_value,
                        changed_at=now,
                    )
                )
                trip_reminder_enabled = new_value

        if "marketing_enabled" in request.model_fields_set:
            new_value = request.marketing_enabled

            if (
                new_value is not None
                and new_value != marketing_enabled
            ):
                histories.append(
                    NotificationConsentHistoryDocument(
                        consent_type=(
                            NotificationConsentType.MARKETING
                        ),
                        previous_enabled=marketing_enabled,
                        enabled=new_value,
                        changed_at=now,
                    )
                )
                marketing_enabled = new_value

        settings = NotificationSettingsDocument(
            game_reminder_enabled=game_reminder_enabled,
            trip_reminder_enabled=trip_reminder_enabled,
            marketing_enabled=marketing_enabled,
            updated_at=now,
        )

        self._repository.save_settings_with_history(
            user_id=user_id,
            settings=settings,
            histories=histories,
        )

        return self._to_response(settings)

    def get_history(
        self,
        *,
        user_id: str,
    ) -> list[NotificationConsentHistoryResponse]:
        histories = self._repository.get_history(user_id)

        return [
            NotificationConsentHistoryResponse(
                history_id=history.history_id,
                consent_type=history.consent_type,
                previous_enabled=history.previous_enabled,
                enabled=history.enabled,
                changed_at=history.changed_at,
            )
            for history in histories
        ]

    @staticmethod
    def _create_default_settings(
    ) -> NotificationSettingsDocument:
        return NotificationSettingsDocument(
            game_reminder_enabled=True,
            trip_reminder_enabled=True,
            marketing_enabled=False,
            updated_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _to_response(
        settings: NotificationSettingsDocument,
    ) -> NotificationSettingsResponse:
        return NotificationSettingsResponse(
            game_reminder_enabled=(
                settings.game_reminder_enabled
            ),
            trip_reminder_enabled=(
                settings.trip_reminder_enabled
            ),
            marketing_enabled=settings.marketing_enabled,
            updated_at=settings.updated_at,
        )

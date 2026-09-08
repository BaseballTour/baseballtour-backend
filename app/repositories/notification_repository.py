from uuid import uuid4

from google.cloud.firestore_v1.client import Client

from app.core.firebase import get_firestore_client
from app.schemas.notification import (
    NotificationConsentHistoryDocument,
    NotificationConsentHistoryRecord,
    NotificationSettingsDocument,
)


class NotificationRepository:
    """사용자 알림 설정과 변경 이력 Firestore 접근을 담당합니다."""

    USERS_COLLECTION = "users"
    SETTINGS_COLLECTION = "settings"
    SETTINGS_DOCUMENT = "notifications"
    HISTORY_COLLECTION = "notificationConsentHistory"

    def __init__(
        self,
        client: Client | None = None,
    ) -> None:
        self._client = client or get_firestore_client()
        self._users = self._client.collection(
            self.USERS_COLLECTION
        )

    def _settings_document(self, user_id: str):
        return (
            self._users
            .document(user_id)
            .collection(self.SETTINGS_COLLECTION)
            .document(self.SETTINGS_DOCUMENT)
        )

    def _history_collection(self, user_id: str):
        return (
            self._users
            .document(user_id)
            .collection(self.HISTORY_COLLECTION)
        )

    def get_settings(
        self,
        user_id: str,
    ) -> NotificationSettingsDocument | None:
        document = self._settings_document(user_id).get()

        if not document.exists:
            return None

        return NotificationSettingsDocument.model_validate(
            document.to_dict() or {}
        )

    def save_settings(
        self,
        *,
        user_id: str,
        settings: NotificationSettingsDocument,
    ) -> None:
        self._settings_document(user_id).set(
            settings.model_dump(
                by_alias=True,
                exclude_none=False,
            )
        )

    def save_settings_with_history(
        self,
        *,
        user_id: str,
        settings: NotificationSettingsDocument,
        histories: list[
            NotificationConsentHistoryDocument
        ],
    ) -> None:
        """설정과 변경 이력을 하나의 batch로 저장합니다."""
        batch = self._client.batch()

        batch.set(
            self._settings_document(user_id),
            settings.model_dump(
                by_alias=True,
                exclude_none=False,
            ),
        )

        history_collection = self._history_collection(
            user_id
        )

        for history in histories:
            history_id = f"history_{uuid4().hex}"

            batch.set(
                history_collection.document(history_id),
                history.model_dump(
                    by_alias=True,
                    exclude_none=False,
                ),
            )

        batch.commit()

    def get_history(
        self,
        user_id: str,
    ) -> list[NotificationConsentHistoryRecord]:
        histories: list[
            NotificationConsentHistoryRecord
        ] = []

        for document in self._history_collection(
            user_id
        ).stream():
            data = document.to_dict() or {}

            histories.append(
                NotificationConsentHistoryRecord(
                    history_id=document.id,
                    **data,
                )
            )

        return sorted(
            histories,
            key=lambda history: (
                history.changed_at,
                history.history_id,
            ),
            reverse=True,
        )

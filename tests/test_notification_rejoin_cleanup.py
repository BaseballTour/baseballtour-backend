from unittest.mock import MagicMock

from app.repositories.notification_inbox_repository import (
    NotificationInboxRepository,
)
from app.repositories.notification_repository import (
    NotificationRepository,
)


def test_notification_repository_deletes_settings_and_history() -> None:
    client = MagicMock()
    users = MagicMock()
    user = MagicMock()
    settings = MagicMock()
    settings_document = MagicMock()
    histories = MagicMock()

    history_a = MagicMock()
    history_b = MagicMock()

    client.collection.return_value = users
    users.document.return_value = user

    def collection_side_effect(name):
        if name == "settings":
            return settings
        if name == "notificationConsentHistory":
            return histories
        raise AssertionError(name)

    user.collection.side_effect = collection_side_effect
    settings.document.return_value = settings_document
    histories.stream.return_value = [
        history_a,
        history_b,
    ]

    repository = NotificationRepository(
        client=client
    )

    repository.delete_all_by_user_id(
        user_id="firebase-user-123"
    )

    settings.document.assert_called_once_with(
        "notifications"
    )
    settings_document.delete.assert_called_once_with()

    history_a.reference.delete.assert_called_once_with()
    history_b.reference.delete.assert_called_once_with()


def test_notification_inbox_repository_deletes_all_notifications() -> None:
    client = MagicMock()
    users = MagicMock()
    user = MagicMock()
    notifications = MagicMock()

    notification_a = MagicMock()
    notification_b = MagicMock()

    client.collection.return_value = users
    users.document.return_value = user
    user.collection.return_value = notifications

    notifications.stream.return_value = [
        notification_a,
        notification_b,
    ]

    repository = NotificationInboxRepository(
        client=client
    )

    repository.delete_all_by_user_id(
        user_id="firebase-user-123"
    )

    user.collection.assert_called_once_with(
        "notifications"
    )

    notification_a.reference.delete.assert_called_once_with()
    notification_b.reference.delete.assert_called_once_with()

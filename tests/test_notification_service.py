from datetime import datetime, timezone
from unittest.mock import Mock

from app.repositories.notification_repository import (
    NotificationRepository,
)
from app.schemas.notification import (
    NotificationConsentHistoryDocument,
    NotificationConsentHistoryRecord,
    NotificationConsentType,
    NotificationSettingsDocument,
    NotificationSettingsUpdateRequest,
)
from app.services.notification_service import (
    NotificationService,
)


def make_settings(
    *,
    game: bool = True,
    trip: bool = True,
    marketing: bool = False,
) -> NotificationSettingsDocument:
    return NotificationSettingsDocument(
        game_reminder_enabled=game,
        trip_reminder_enabled=trip,
        marketing_enabled=marketing,
        updated_at=datetime(
            2026,
            9,
            7,
            8,
            0,
            tzinfo=timezone.utc,
        ),
    )


def test_get_settings_creates_defaults_when_missing() -> None:
    repository = Mock()
    repository.get_settings.return_value = None
    service = NotificationService(repository=repository)

    response = service.get_settings(
        user_id="user_001",
    )

    assert response.game_reminder_enabled is True
    assert response.trip_reminder_enabled is True
    assert response.marketing_enabled is False

    repository.save_settings.assert_called_once()

    call = repository.save_settings.call_args
    assert call.kwargs["user_id"] == "user_001"

    saved = call.kwargs["settings"]
    assert saved.game_reminder_enabled is True
    assert saved.trip_reminder_enabled is True
    assert saved.marketing_enabled is False


def test_get_settings_returns_existing_settings() -> None:
    repository = Mock()
    repository.get_settings.return_value = make_settings(
        game=False,
        trip=True,
        marketing=True,
    )
    service = NotificationService(repository=repository)

    response = service.get_settings(
        user_id="user_001",
    )

    assert response.game_reminder_enabled is False
    assert response.trip_reminder_enabled is True
    assert response.marketing_enabled is True

    repository.save_settings.assert_not_called()


def test_update_settings_changes_single_field_and_creates_history() -> None:
    repository = Mock()
    repository.get_settings.return_value = make_settings()
    service = NotificationService(repository=repository)

    response = service.update_settings(
        user_id="user_001",
        request=NotificationSettingsUpdateRequest(
            marketing_enabled=True,
        ),
    )

    assert response.game_reminder_enabled is True
    assert response.trip_reminder_enabled is True
    assert response.marketing_enabled is True

    call = repository.save_settings_with_history.call_args
    assert call.kwargs["user_id"] == "user_001"

    histories = call.kwargs["histories"]

    assert len(histories) == 1
    assert (
        histories[0].consent_type
        == NotificationConsentType.MARKETING
    )
    assert histories[0].previous_enabled is False
    assert histories[0].enabled is True


def test_update_settings_does_not_create_history_for_same_value() -> None:
    repository = Mock()
    repository.get_settings.return_value = make_settings()
    service = NotificationService(repository=repository)

    response = service.update_settings(
        user_id="user_001",
        request=NotificationSettingsUpdateRequest(
            marketing_enabled=False,
        ),
    )

    assert response.marketing_enabled is False

    call = repository.save_settings_with_history.call_args
    assert call.kwargs["histories"] == []


def test_update_settings_creates_history_for_each_changed_field() -> None:
    repository = Mock()
    repository.get_settings.return_value = make_settings()
    service = NotificationService(repository=repository)

    response = service.update_settings(
        user_id="user_001",
        request=NotificationSettingsUpdateRequest(
            game_reminder_enabled=False,
            trip_reminder_enabled=False,
            marketing_enabled=True,
        ),
    )

    assert response.game_reminder_enabled is False
    assert response.trip_reminder_enabled is False
    assert response.marketing_enabled is True

    histories = (
        repository
        .save_settings_with_history
        .call_args
        .kwargs["histories"]
    )

    assert len(histories) == 3

    assert {
        history.consent_type
        for history in histories
    } == {
        NotificationConsentType.GAME_REMINDER,
        NotificationConsentType.TRIP_REMINDER,
        NotificationConsentType.MARKETING,
    }


def test_update_settings_uses_defaults_when_document_missing() -> None:
    repository = Mock()
    repository.get_settings.return_value = None
    service = NotificationService(repository=repository)

    response = service.update_settings(
        user_id="user_001",
        request=NotificationSettingsUpdateRequest(
            game_reminder_enabled=False,
        ),
    )

    assert response.game_reminder_enabled is False
    assert response.trip_reminder_enabled is True
    assert response.marketing_enabled is False

    histories = (
        repository
        .save_settings_with_history
        .call_args
        .kwargs["histories"]
    )

    assert len(histories) == 1
    assert (
        histories[0].consent_type
        == NotificationConsentType.GAME_REMINDER
    )
    assert histories[0].previous_enabled is True
    assert histories[0].enabled is False


def test_get_history_maps_repository_records() -> None:
    repository = Mock()

    changed_at = datetime(
        2026,
        9,
        7,
        8,
        0,
        tzinfo=timezone.utc,
    )

    repository.get_history.return_value = [
        NotificationConsentHistoryRecord(
            history_id="history_001",
            consent_type=NotificationConsentType.MARKETING,
            previous_enabled=False,
            enabled=True,
            changed_at=changed_at,
        )
    ]

    service = NotificationService(repository=repository)

    histories = service.get_history(
        user_id="user_001",
    )

    assert len(histories) == 1
    assert histories[0].history_id == "history_001"
    assert (
        histories[0].consent_type
        == NotificationConsentType.MARKETING
    )


def test_repository_get_history_sorts_latest_first() -> None:
    client = Mock()
    users = client.collection.return_value
    user_document = users.document.return_value
    history_collection = user_document.collection.return_value

    older = Mock()
    older.id = "history_old"
    older.to_dict.return_value = {
        "consentType": "MARKETING",
        "previousEnabled": False,
        "enabled": True,
        "changedAt": datetime(
            2026,
            9,
            6,
            8,
            0,
            tzinfo=timezone.utc,
        ),
    }

    newer = Mock()
    newer.id = "history_new"
    newer.to_dict.return_value = {
        "consentType": "GAME_REMINDER",
        "previousEnabled": True,
        "enabled": False,
        "changedAt": datetime(
            2026,
            9,
            7,
            8,
            0,
            tzinfo=timezone.utc,
        ),
    }

    history_collection.stream.return_value = [
        older,
        newer,
    ]

    repository = NotificationRepository(client=client)

    histories = repository.get_history("user_001")

    assert [
        history.history_id
        for history in histories
    ] == [
        "history_new",
        "history_old",
    ]


def test_repository_saves_settings_and_histories_in_batch() -> None:
    client = Mock()
    batch = client.batch.return_value

    repository = NotificationRepository(client=client)

    now = datetime(
        2026,
        9,
        7,
        8,
        0,
        tzinfo=timezone.utc,
    )

    histories = [
        NotificationConsentHistoryDocument(
            consent_type=NotificationConsentType.GAME_REMINDER,
            previous_enabled=True,
            enabled=False,
            changed_at=now,
        ),
        NotificationConsentHistoryDocument(
            consent_type=NotificationConsentType.MARKETING,
            previous_enabled=False,
            enabled=True,
            changed_at=now,
        ),
    ]

    repository.save_settings_with_history(
        user_id="user_001",
        settings=make_settings(
            game=False,
            marketing=True,
        ),
        histories=histories,
    )

    # 설정 문서 1개 + 이력 문서 2개
    assert batch.set.call_count == 3
    batch.commit.assert_called_once_with()

from datetime import datetime, timezone
from unittest.mock import Mock

from app.repositories.notification_repository import (
    NotificationRepository,
)
from app.schemas.notification import (
    NotificationConsentHistoryDocument,
    NotificationConsentHistoryRecord,
    NotificationConsentType,
    NotificationSettingsDocument,
    NotificationSettingsUpdateRequest,
)
from app.services.notification_service import (
    NotificationService,
)


def make_settings(
    *,
    game: bool = True,
    trip: bool = True,
    marketing: bool = False,
) -> NotificationSettingsDocument:
    return NotificationSettingsDocument(
        game_reminder_enabled=game,
        trip_reminder_enabled=trip,
        marketing_enabled=marketing,
        updated_at=datetime(
            2026,
            9,
            7,
            8,
            0,
            tzinfo=timezone.utc,
        ),
    )


def test_get_settings_creates_defaults_when_missing() -> None:
    repository = Mock()
    repository.get_settings.return_value = None
    service = NotificationService(repository=repository)

    response = service.get_settings(
        user_id="user_001",
    )

    assert response.game_reminder_enabled is True
    assert response.trip_reminder_enabled is True
    assert response.marketing_enabled is False

    repository.save_settings.assert_called_once()

    call = repository.save_settings.call_args
    assert call.kwargs["user_id"] == "user_001"

    saved = call.kwargs["settings"]
    assert saved.game_reminder_enabled is True
    assert saved.trip_reminder_enabled is True
    assert saved.marketing_enabled is False


def test_get_settings_returns_existing_settings() -> None:
    repository = Mock()
    repository.get_settings.return_value = make_settings(
        game=False,
        trip=True,
        marketing=True,
    )
    service = NotificationService(repository=repository)

    response = service.get_settings(
        user_id="user_001",
    )

    assert response.game_reminder_enabled is False
    assert response.trip_reminder_enabled is True
    assert response.marketing_enabled is True

    repository.save_settings.assert_not_called()


def test_update_settings_changes_single_field_and_creates_history() -> None:
    repository = Mock()
    repository.get_settings.return_value = make_settings()
    service = NotificationService(repository=repository)

    response = service.update_settings(
        user_id="user_001",
        request=NotificationSettingsUpdateRequest(
            marketing_enabled=True,
        ),
    )

    assert response.game_reminder_enabled is True
    assert response.trip_reminder_enabled is True
    assert response.marketing_enabled is True

    call = repository.save_settings_with_history.call_args
    assert call.kwargs["user_id"] == "user_001"

    histories = call.kwargs["histories"]

    assert len(histories) == 1
    assert (
        histories[0].consent_type
        == NotificationConsentType.MARKETING
    )
    assert histories[0].previous_enabled is False
    assert histories[0].enabled is True


def test_update_settings_does_not_create_history_for_same_value() -> None:
    repository = Mock()
    repository.get_settings.return_value = make_settings()
    service = NotificationService(repository=repository)

    response = service.update_settings(
        user_id="user_001",
        request=NotificationSettingsUpdateRequest(
            marketing_enabled=False,
        ),
    )

    assert response.marketing_enabled is False

    call = repository.save_settings_with_history.call_args
    assert call.kwargs["histories"] == []


def test_update_settings_creates_history_for_each_changed_field() -> None:
    repository = Mock()
    repository.get_settings.return_value = make_settings()
    service = NotificationService(repository=repository)

    response = service.update_settings(
        user_id="user_001",
        request=NotificationSettingsUpdateRequest(
            game_reminder_enabled=False,
            trip_reminder_enabled=False,
            marketing_enabled=True,
        ),
    )

    assert response.game_reminder_enabled is False
    assert response.trip_reminder_enabled is False
    assert response.marketing_enabled is True

    histories = (
        repository
        .save_settings_with_history
        .call_args
        .kwargs["histories"]
    )

    assert len(histories) == 3

    assert {
        history.consent_type
        for history in histories
    } == {
        NotificationConsentType.GAME_REMINDER,
        NotificationConsentType.TRIP_REMINDER,
        NotificationConsentType.MARKETING,
    }


def test_update_settings_uses_defaults_when_document_missing() -> None:
    repository = Mock()
    repository.get_settings.return_value = None
    service = NotificationService(repository=repository)

    response = service.update_settings(
        user_id="user_001",
        request=NotificationSettingsUpdateRequest(
            game_reminder_enabled=False,
        ),
    )

    assert response.game_reminder_enabled is False
    assert response.trip_reminder_enabled is True
    assert response.marketing_enabled is False

    histories = (
        repository
        .save_settings_with_history
        .call_args
        .kwargs["histories"]
    )

    assert len(histories) == 1
    assert (
        histories[0].consent_type
        == NotificationConsentType.GAME_REMINDER
    )
    assert histories[0].previous_enabled is True
    assert histories[0].enabled is False


def test_get_history_maps_repository_records() -> None:
    repository = Mock()

    changed_at = datetime(
        2026,
        9,
        7,
        8,
        0,
        tzinfo=timezone.utc,
    )

    repository.get_history.return_value = [
        NotificationConsentHistoryRecord(
            history_id="history_001",
            consent_type=NotificationConsentType.MARKETING,
            previous_enabled=False,
            enabled=True,
            changed_at=changed_at,
        )
    ]

    service = NotificationService(repository=repository)

    histories = service.get_history(
        user_id="user_001",
    )

    assert len(histories) == 1
    assert histories[0].history_id == "history_001"
    assert (
        histories[0].consent_type
        == NotificationConsentType.MARKETING
    )


def test_repository_get_history_sorts_latest_first() -> None:
    client = Mock()
    users = client.collection.return_value
    user_document = users.document.return_value
    history_collection = user_document.collection.return_value

    older = Mock()
    older.id = "history_old"
    older.to_dict.return_value = {
        "consentType": "MARKETING",
        "previousEnabled": False,
        "enabled": True,
        "changedAt": datetime(
            2026,
            9,
            6,
            8,
            0,
            tzinfo=timezone.utc,
        ),
    }

    newer = Mock()
    newer.id = "history_new"
    newer.to_dict.return_value = {
        "consentType": "GAME_REMINDER",
        "previousEnabled": True,
        "enabled": False,
        "changedAt": datetime(
            2026,
            9,
            7,
            8,
            0,
            tzinfo=timezone.utc,
        ),
    }

    history_collection.stream.return_value = [
        older,
        newer,
    ]

    repository = NotificationRepository(client=client)

    histories = repository.get_history("user_001")

    assert [
        history.history_id
        for history in histories
    ] == [
        "history_new",
        "history_old",
    ]


def test_repository_saves_settings_and_histories_in_batch() -> None:
    client = Mock()
    batch = client.batch.return_value

    repository = NotificationRepository(client=client)

    now = datetime(
        2026,
        9,
        7,
        8,
        0,
        tzinfo=timezone.utc,
    )

    histories = [
        NotificationConsentHistoryDocument(
            consent_type=NotificationConsentType.GAME_REMINDER,
            previous_enabled=True,
            enabled=False,
            changed_at=now,
        ),
        NotificationConsentHistoryDocument(
            consent_type=NotificationConsentType.MARKETING,
            previous_enabled=False,
            enabled=True,
            changed_at=now,
        ),
    ]

    repository.save_settings_with_history(
        user_id="user_001",
        settings=make_settings(
            game=False,
            marketing=True,
        ),
        histories=histories,
    )

    # 설정 문서 1개 + 이력 문서 2개
    assert batch.set.call_count == 3
    batch.commit.assert_called_once_with()

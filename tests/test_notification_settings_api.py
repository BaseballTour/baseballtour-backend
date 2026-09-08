from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.dependencies.auth import (
    get_current_active_user_context,
)
from app.main import app
from app.schemas.notification import (
    NotificationConsentHistoryResponse,
    NotificationConsentType,
    NotificationSettingsResponse,
)


client = TestClient(app)


def override_active_user():
    return SimpleNamespace(
        user_id="firebase_uid_test",
    )


def make_settings() -> NotificationSettingsResponse:
    return NotificationSettingsResponse(
        game_reminder_enabled=True,
        trip_reminder_enabled=True,
        marketing_enabled=False,
        updated_at=datetime(
            2026,
            9,
            7,
            8,
            0,
            tzinfo=timezone.utc,
        ),
    )


def test_get_notification_settings_returns_response() -> None:
    app.dependency_overrides[
        get_current_active_user_context
    ] = override_active_user

    try:
        with patch(
            "app.api.v1.endpoints.notification_settings."
            "NotificationService"
        ) as service_class:
            get_settings = (
                service_class.return_value.get_settings
            )
            get_settings.return_value = make_settings()

            response = client.get(
                "/api/v1/users/me/notification-settings"
            )

        assert response.status_code == 200

        body = response.json()

        assert body["success"] is True
        assert body["data"]["gameReminderEnabled"] is True
        assert body["data"]["tripReminderEnabled"] is True
        assert body["data"]["marketingEnabled"] is False

        get_settings.assert_called_once_with(
            user_id="firebase_uid_test",
        )
    finally:
        app.dependency_overrides.clear()


def test_patch_notification_settings_forwards_request() -> None:
    app.dependency_overrides[
        get_current_active_user_context
    ] = override_active_user

    try:
        updated = NotificationSettingsResponse(
            game_reminder_enabled=True,
            trip_reminder_enabled=True,
            marketing_enabled=True,
            updated_at=datetime(
                2026,
                9,
                7,
                8,
                0,
                tzinfo=timezone.utc,
            ),
        )

        with patch(
            "app.api.v1.endpoints.notification_settings."
            "NotificationService"
        ) as service_class:
            update_settings = (
                service_class.return_value.update_settings
            )
            update_settings.return_value = updated

            response = client.patch(
                "/api/v1/users/me/notification-settings",
                json={
                    "marketingEnabled": True,
                },
            )

        assert response.status_code == 200
        assert (
            response.json()["data"]["marketingEnabled"]
            is True
        )

        call = update_settings.call_args

        assert call.kwargs["user_id"] == "firebase_uid_test"

        request = call.kwargs["request"]
        assert request.marketing_enabled is True
        assert request.model_fields_set == {
            "marketing_enabled"
        }
    finally:
        app.dependency_overrides.clear()


def test_patch_notification_settings_rejects_empty_body() -> None:
    app.dependency_overrides[
        get_current_active_user_context
    ] = override_active_user

    try:
        response = client.patch(
            "/api/v1/users/me/notification-settings",
            json={},
        )

        assert response.status_code == 422
        assert (
            response.json()["error"]["code"]
            == "VALIDATION_ERROR"
        )
    finally:
        app.dependency_overrides.clear()


def test_patch_notification_settings_rejects_null() -> None:
    app.dependency_overrides[
        get_current_active_user_context
    ] = override_active_user

    try:
        response = client.patch(
            "/api/v1/users/me/notification-settings",
            json={
                "marketingEnabled": None,
            },
        )

        assert response.status_code == 422
        assert (
            response.json()["error"]["code"]
            == "VALIDATION_ERROR"
        )
    finally:
        app.dependency_overrides.clear()


def test_get_notification_consent_history_returns_list() -> None:
    app.dependency_overrides[
        get_current_active_user_context
    ] = override_active_user

    try:
        history = NotificationConsentHistoryResponse(
            history_id="history_001",
            consent_type=NotificationConsentType.MARKETING,
            previous_enabled=False,
            enabled=True,
            changed_at=datetime(
                2026,
                9,
                7,
                8,
                0,
                tzinfo=timezone.utc,
            ),
        )

        with patch(
            "app.api.v1.endpoints.notification_settings."
            "NotificationService"
        ) as service_class:
            get_history = (
                service_class.return_value.get_history
            )
            get_history.return_value = [history]

            response = client.get(
                "/api/v1/users/me/"
                "notification-consent-history"
            )

        assert response.status_code == 200

        body = response.json()

        assert body["success"] is True
        assert body["meta"] == {
            "count": 1,
            "nextPageToken": None,
        }
        assert (
            body["data"][0]["consentType"]
            == "MARKETING"
        )
        assert body["data"][0]["previousEnabled"] is False
        assert body["data"][0]["enabled"] is True

        get_history.assert_called_once_with(
            user_id="firebase_uid_test",
        )
    finally:
        app.dependency_overrides.clear()

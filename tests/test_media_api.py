from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import (
    get_current_active_user_id,
)
from app.main import app
from app.schemas.media import (
    MediaUploadUrlResponse,
)


USER_ID = "firebase-user-123"


@pytest.fixture
def authenticated_client() -> TestClient:
    app.dependency_overrides[
        get_current_active_user_id
    ] = lambda: USER_ID

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_create_profile_media_upload_url(
    authenticated_client: TestClient,
) -> None:
    service = Mock()

    service.create_upload_url.return_value = (
        MediaUploadUrlResponse(
            upload_url=(
                "https://storage.example/upload"
            ),
            storage_path=(
                "users/firebase-user-123/"
                "profile/media_001.jpg"
            ),
            content_type="image/jpeg",
            expires_in_seconds=900,
            required_headers={
                "Content-Type": "image/jpeg",
            },
        )
    )

    with patch(
        (
            "app.api.v1.endpoints.media."
            "StorageService"
        ),
        return_value=service,
    ):
        response = authenticated_client.post(
            "/api/v1/media/upload-urls",
            json={
                "purpose": "PROFILE_IMAGE",
                "fileName": "profile.jpg",
                "contentType": "image/jpeg",
                "fileSizeBytes": 1024,
            },
        )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert (
        body["data"]["uploadUrl"]
        == "https://storage.example/upload"
    )
    assert (
        body["data"]["contentType"]
        == "image/jpeg"
    )
    assert (
        body["data"]["expiresInSeconds"]
        == 900
    )
    assert body["data"]["requiredHeaders"] == {
        "Content-Type": "image/jpeg",
    }

    service.create_upload_url.assert_called_once()

    kwargs = (
        service.create_upload_url
        .call_args.kwargs
    )

    assert kwargs["user_id"] == USER_ID
    assert (
        kwargs["request"].purpose.value
        == "PROFILE_IMAGE"
    )


def test_attendance_media_requires_target_ids(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.post(
        "/api/v1/media/upload-urls",
        json={
            "purpose": "ATTENDANCE_LOG",
            "fileName": "photo.jpg",
            "contentType": "image/jpeg",
            "fileSizeBytes": 1024,
        },
    )

    assert response.status_code == 422
    assert (
        response.json()["error"]["code"]
        == "VALIDATION_ERROR"
    )


def test_profile_media_rejects_attendance_target(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.post(
        "/api/v1/media/upload-urls",
        json={
            "purpose": "PROFILE_IMAGE",
            "fileName": "photo.jpg",
            "contentType": "image/jpeg",
            "fileSizeBytes": 1024,
            "attendanceLogId": "log_001",
            "logEntryId": "entry_001",
        },
    )

    assert response.status_code == 422
    assert (
        response.json()["error"]["code"]
        == "VALIDATION_ERROR"
    )


def test_complete_profile_media_upload(
    authenticated_client: TestClient,
) -> None:
    from app.schemas.media import (
        MediaCompleteResponse,
        MediaPurpose,
    )

    service = Mock()

    service.complete_upload.return_value = (
        MediaCompleteResponse(
            purpose=MediaPurpose.PROFILE_IMAGE,
            storage_path=(
                "users/firebase-user-123/"
                "profile/media_001.jpg"
            ),
            content_type="image/jpeg",
            media_url=(
                "https://storage.example/read"
            ),
            log_media_id=None,
            sequence_no=None,
        )
    )

    with patch(
        (
            "app.api.v1.endpoints.media."
            "StorageService"
        ),
        return_value=service,
    ):
        response = authenticated_client.post(
            "/api/v1/media/complete",
            json={
                "purpose": "PROFILE_IMAGE",
                "storagePath": (
                    "users/firebase-user-123/"
                    "profile/media_001.jpg"
                ),
                "contentType": "image/jpeg",
            },
        )

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True

    assert (
        body["data"]["mediaUrl"]
        == "https://storage.example/read"
    )

    service.complete_upload.assert_called_once()

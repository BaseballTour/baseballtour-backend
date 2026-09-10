from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies.auth import (
    get_current_active_user_id,
)
from app.api.v1.endpoints import (
    attendance_logs as attendance_logs_endpoint,
)
from app.core.exceptions import AppException
from app.main import app
from app.repositories.attendance_log_repository import (
    AttendanceLogCoverImageConflictError,
)
from app.schemas.attendance_log import (
    AttendanceLogRecord,
    AttendanceLogStatus,
    AttendanceLogVisibility,
)
from app.schemas.media import (
    MediaCompleteRequest,
    MediaPurpose,
    MediaUploadUrlRequest,
)
from app.services.attendance_log_service import (
    AttendanceLogService,
)
from app.services.storage_service import StorageService


USER_ID = "firebase-user-123"
LOG_ID = "log_001"

NOW = datetime(
    2026,
    9,
    11,
    0,
    0,
    tzinfo=timezone.utc,
)

OLD_PATH = (
    f"users/{USER_ID}/attendance-logs/"
    f"{LOG_ID}/cover/media_old.jpg"
)

NEW_PATH = (
    f"users/{USER_ID}/attendance-logs/"
    f"{LOG_ID}/cover/media_new.jpg"
)


def make_log(
    *,
    cover_path: str | None = None,
) -> AttendanceLogRecord:
    return AttendanceLogRecord(
        attendance_log_id=LOG_ID,
        user_id=USER_ID,
        trip_id="trip_001",
        game_id="game_001",
        plan_id="plan_001",
        support_team_id="lotte",
        log_title="사직 원정 직관 기록",
        summary_text=None,
        seat=None,
        mate=None,
        cover_image_storage_path=cover_path,
        log_status=AttendanceLogStatus.DRAFT,
        visibility=AttendanceLogVisibility.PRIVATE,
        created_at=NOW,
        updated_at=NOW,
        deleted_at=None,
    )


def make_storage_context(
    *,
    cover_path: str | None = None,
    owner: str = USER_ID,
):
    bucket = Mock()
    blob = Mock()

    bucket.blob.return_value = blob
    blob.generate_signed_url.return_value = (
        "https://storage.example/signed"
    )

    attendance_repository = Mock()
    attendance_repository.get_by_id.return_value = (
        SimpleNamespace(
            user_id=owner,
            cover_image_storage_path=cover_path,
        )
    )

    session_repository = Mock()

    service = StorageService(
        bucket=bucket,
        attendance_log_repository=(
            attendance_repository
        ),
        log_entry_repository=Mock(),
        media_upload_session_repository=(
            session_repository
        ),
    )

    return SimpleNamespace(
        service=service,
        bucket=bucket,
        blob=blob,
        attendance_repository=attendance_repository,
        session_repository=session_repository,
    )


def test_create_cover_upload_url() -> None:
    context = make_storage_context(
        cover_path=OLD_PATH
    )

    result = context.service.create_upload_url(
        user_id=USER_ID,
        request=MediaUploadUrlRequest(
            purpose=(
                MediaPurpose.ATTENDANCE_LOG_COVER_IMAGE
            ),
            file_name="cover.jpg",
            content_type="image/jpeg",
            file_size_bytes=1024,
            attendance_log_id=LOG_ID,
        ),
    )

    assert result.storage_path.startswith(
        f"users/{USER_ID}/attendance-logs/"
        f"{LOG_ID}/cover/"
    )
    assert result.storage_path.endswith(".jpg")

    assert (
        result.expected_cover_image_storage_path
        == OLD_PATH
    )

    context.session_repository.create.assert_called_once()

    kwargs = (
        context.session_repository
        .create.call_args.kwargs
    )

    assert kwargs["user_id"] == USER_ID
    assert kwargs["attendance_log_id"] == LOG_ID
    assert kwargs["expected_storage_path"] == OLD_PATH
    assert "trip_id" not in kwargs


def test_create_cover_upload_url_rejects_other_owner() -> None:
    context = make_storage_context(
        owner="another-user"
    )

    with pytest.raises(AppException) as captured:
        context.service.create_upload_url(
            user_id=USER_ID,
            request=MediaUploadUrlRequest(
                purpose=(
                    MediaPurpose
                    .ATTENDANCE_LOG_COVER_IMAGE
                ),
                file_name="cover.jpg",
                content_type="image/jpeg",
                file_size_bytes=1024,
                attendance_log_id=LOG_ID,
            ),
        )

    assert captured.value.status_code == 403
    assert (
        captured.value.code
        == "ATTENDANCE_LOG_ACCESS_DENIED"
    )


def test_cover_upload_rejects_video() -> None:
    context = make_storage_context()

    with pytest.raises(AppException) as captured:
        context.service.create_upload_url(
            user_id=USER_ID,
            request=MediaUploadUrlRequest(
                purpose=(
                    MediaPurpose
                    .ATTENDANCE_LOG_COVER_IMAGE
                ),
                file_name="cover.mp4",
                content_type="video/mp4",
                file_size_bytes=1024,
                attendance_log_id=LOG_ID,
            ),
        )

    assert captured.value.status_code == 400
    assert (
        captured.value.code
        == "MEDIA_CONTENT_TYPE_UNSUPPORTED"
    )


def configure_complete_context(
    *,
    current_cover_path: str | None,
    expected_cover_path: str | None,
):
    context = make_storage_context(
        cover_path=current_cover_path
    )

    context.blob.content_type = "image/jpeg"
    context.blob.size = 1024

    context.session_repository.get_by_storage_path.return_value = {
        "userId": USER_ID,
        "attendanceLogId": LOG_ID,
        "storagePath": NEW_PATH,
        "expectedCoverImageStoragePath": (
            expected_cover_path
        ),
        "contentType": "image/jpeg",
        "createdAt": datetime.now(timezone.utc),
        "expiresAt": (
            datetime.now(timezone.utc)
            + timedelta(minutes=30)
        ),
    }

    context.attendance_repository.replace_cover_image.return_value = (
        make_log(cover_path=NEW_PATH),
        current_cover_path,
    )

    return context


def test_complete_cover_first_upload() -> None:
    context = configure_complete_context(
        current_cover_path=None,
        expected_cover_path=None,
    )

    result = context.service.complete_upload(
        user_id=USER_ID,
        request=MediaCompleteRequest(
            purpose=(
                MediaPurpose.ATTENDANCE_LOG_COVER_IMAGE
            ),
            storage_path=NEW_PATH,
            content_type="image/jpeg",
            attendance_log_id=LOG_ID,
            expected_cover_image_storage_path=None,
        ),
    )

    assert result.storage_path == NEW_PATH
    assert result.media_url == (
        "https://storage.example/signed"
    )
    assert result.log_media_id is None
    assert result.sequence_no is None

    (
        context.attendance_repository
        .replace_cover_image
        .assert_called_once()
    )

    kwargs = (
        context.attendance_repository
        .replace_cover_image.call_args.kwargs
    )

    assert kwargs["attendance_log_id"] == LOG_ID
    assert kwargs["user_id"] == USER_ID
    assert kwargs["expected_storage_path"] is None
    assert kwargs["storage_path"] == NEW_PATH


def test_complete_cover_replaces_existing_image() -> None:
    context = configure_complete_context(
        current_cover_path=OLD_PATH,
        expected_cover_path=OLD_PATH,
    )

    context.service.complete_upload(
        user_id=USER_ID,
        request=MediaCompleteRequest(
            purpose=(
                MediaPurpose.ATTENDANCE_LOG_COVER_IMAGE
            ),
            storage_path=NEW_PATH,
            content_type="image/jpeg",
            attendance_log_id=LOG_ID,
            expected_cover_image_storage_path=OLD_PATH,
        ),
    )

    kwargs = (
        context.attendance_repository
        .replace_cover_image.call_args.kwargs
    )

    assert kwargs["expected_storage_path"] == OLD_PATH
    assert kwargs["storage_path"] == NEW_PATH


def test_complete_cover_maps_stale_update_to_409() -> None:
    context = configure_complete_context(
        current_cover_path=OLD_PATH,
        expected_cover_path=OLD_PATH,
    )

    context.attendance_repository.replace_cover_image.side_effect = (
        AttendanceLogCoverImageConflictError()
    )

    with pytest.raises(AppException) as captured:
        context.service.complete_upload(
            user_id=USER_ID,
            request=MediaCompleteRequest(
                purpose=(
                    MediaPurpose
                    .ATTENDANCE_LOG_COVER_IMAGE
                ),
                storage_path=NEW_PATH,
                content_type="image/jpeg",
                attendance_log_id=LOG_ID,
                expected_cover_image_storage_path=(
                    OLD_PATH
                ),
            ),
        )

    assert captured.value.status_code == 409
    assert (
        captured.value.code
        == "ATTENDANCE_LOG_COVER_IMAGE_CONFLICT"
    )


def test_log_response_uses_log_cover_image() -> None:
    service = object.__new__(
        AttendanceLogService
    )

    storage_service = Mock()
    storage_service.create_download_url.return_value = (
        "https://storage.example/log-cover"
    )

    service._storage_service = storage_service

    result = service._to_log_response_with_cover(
        make_log(cover_path=OLD_PATH)
    )

    assert result.cover_image_url == (
        "https://storage.example/log-cover"
    )

    storage_service.create_download_url.assert_called_once_with(
        OLD_PATH
    )


def test_log_response_does_not_fallback_to_entry_media() -> None:
    service = object.__new__(
        AttendanceLogService
    )

    storage_service = Mock()
    service._storage_service = storage_service

    result = service._to_log_response_with_cover(
        make_log(cover_path=None)
    )

    assert result.cover_image_url is None

    (
        storage_service
        .create_download_url
        .assert_not_called()
    )


def test_delete_cover_image_service() -> None:
    repository = Mock()

    repository.clear_cover_image.return_value = (
        make_log(cover_path=None),
        OLD_PATH,
    )

    service = object.__new__(
        AttendanceLogService
    )
    service._attendance_log_repository = repository

    storage_service = Mock()
    service._storage_service = storage_service

    service.delete_cover_image(
        user_id=USER_ID,
        attendance_log_id=LOG_ID,
    )

    repository.clear_cover_image.assert_called_once()

    kwargs = (
        repository
        .clear_cover_image.call_args.kwargs
    )

    assert kwargs["attendance_log_id"] == LOG_ID
    assert kwargs["user_id"] == USER_ID

    storage_service.delete_storage_path.assert_called_once_with(
        OLD_PATH
    )


def test_delete_cover_image_api(
    monkeypatch,
) -> None:
    called = {}

    class FakeAttendanceLogService:
        def delete_cover_image(
            self,
            *,
            user_id: str,
            attendance_log_id: str,
        ) -> None:
            called["user_id"] = user_id
            called["attendance_log_id"] = (
                attendance_log_id
            )

    monkeypatch.setattr(
        attendance_logs_endpoint,
        "AttendanceLogService",
        FakeAttendanceLogService,
    )

    app.dependency_overrides[
        get_current_active_user_id
    ] = lambda: USER_ID

    try:
        with TestClient(app) as client:
            response = client.delete(
                f"/api/v1/attendance-logs/"
                f"{LOG_ID}/cover-image"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    body = response.json()

    assert body["success"] is True
    assert body["data"]["deleted"] is True

    assert called == {
        "user_id": USER_ID,
        "attendance_log_id": LOG_ID,
    }

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import status

from app.core.exceptions import AppException
from app.schemas.media import (
    MediaPurpose,
    MediaUploadUrlRequest,
)
from app.services.storage_service import (
    PROFILE_IMAGE_MAX_BYTES,
    StorageService,
)


USER_ID = "firebase-user-123"


def make_service(
    *,
    log_user_id: str = USER_ID,
):
    bucket = Mock()
    blob = Mock()

    bucket.blob.return_value = blob
    blob.generate_signed_url.return_value = (
        "https://storage.example/upload"
    )

    attendance_repository = Mock()
    attendance_repository.get_by_id.return_value = (
        SimpleNamespace(
            user_id=log_user_id,
        )
    )

    entry_repository = Mock()
    entry_repository.get_by_id.return_value = (
        SimpleNamespace(
            log_entry_id="entry_001",
        )
    )

    service = StorageService(
        bucket=bucket,
        attendance_log_repository=(
            attendance_repository
        ),
        log_entry_repository=entry_repository,
    )

    return SimpleNamespace(
        service=service,
        bucket=bucket,
        blob=blob,
        attendance_repository=(
            attendance_repository
        ),
        entry_repository=entry_repository,
    )


def test_create_profile_upload_url() -> None:
    context = make_service()

    result = context.service.create_upload_url(
        user_id=USER_ID,
        request=MediaUploadUrlRequest(
            purpose=MediaPurpose.PROFILE_IMAGE,
            file_name="profile.jpg",
            content_type="image/jpeg",
            file_size_bytes=1024,
        ),
    )

    assert result.upload_url == (
        "https://storage.example/upload"
    )
    assert result.content_type == "image/jpeg"
    assert result.expires_in_seconds == 900

    assert result.storage_path.startswith(
        f"users/{USER_ID}/profile/media_"
    )
    assert result.storage_path.endswith(".jpg")

    context.attendance_repository.get_by_id.assert_not_called()
    context.entry_repository.get_by_id.assert_not_called()

    context.blob.generate_signed_url.assert_called_once()

    kwargs = (
        context.blob.generate_signed_url
        .call_args.kwargs
    )

    assert kwargs["version"] == "v4"
    assert kwargs["method"] == "PUT"
    assert kwargs["content_type"] == "image/jpeg"


def test_create_attendance_upload_url_checks_owner_and_entry() -> None:
    context = make_service()

    result = context.service.create_upload_url(
        user_id=USER_ID,
        request=MediaUploadUrlRequest(
            purpose=MediaPurpose.ATTENDANCE_LOG,
            file_name="photo.webp",
            content_type="image/webp",
            file_size_bytes=2048,
            attendance_log_id="log_001",
            log_entry_id="entry_001",
        ),
    )

    assert result.storage_path.startswith(
        (
            f"users/{USER_ID}/attendance-logs/"
            "log_001/entry_001/media_"
        )
    )
    assert result.storage_path.endswith(".webp")

    context.attendance_repository.get_by_id.assert_called_once_with(
        "log_001"
    )

    context.entry_repository.get_by_id.assert_called_once_with(
        "log_001",
        "entry_001",
    )


def test_create_attendance_upload_url_rejects_other_owner() -> None:
    context = make_service(
        log_user_id="another-user"
    )

    with pytest.raises(AppException) as captured:
        context.service.create_upload_url(
            user_id=USER_ID,
            request=MediaUploadUrlRequest(
                purpose=MediaPurpose.ATTENDANCE_LOG,
                file_name="photo.jpg",
                content_type="image/jpeg",
                file_size_bytes=1024,
                attendance_log_id="log_001",
                log_entry_id="entry_001",
            ),
        )

    assert (
        captured.value.status_code
        == status.HTTP_403_FORBIDDEN
    )
    assert (
        captured.value.code
        == "ATTENDANCE_LOG_ACCESS_DENIED"
    )

    context.entry_repository.get_by_id.assert_not_called()


def test_profile_upload_rejects_video() -> None:
    context = make_service()

    with pytest.raises(AppException) as captured:
        context.service.create_upload_url(
            user_id=USER_ID,
            request=MediaUploadUrlRequest(
                purpose=MediaPurpose.PROFILE_IMAGE,
                file_name="profile.mp4",
                content_type="video/mp4",
                file_size_bytes=1024,
            ),
        )

    assert (
        captured.value.code
        == "MEDIA_CONTENT_TYPE_UNSUPPORTED"
    )


def test_upload_rejects_oversized_file() -> None:
    context = make_service()

    with pytest.raises(AppException) as captured:
        context.service.create_upload_url(
            user_id=USER_ID,
            request=MediaUploadUrlRequest(
                purpose=MediaPurpose.PROFILE_IMAGE,
                file_name="profile.jpg",
                content_type="image/jpeg",
                file_size_bytes=(
                    PROFILE_IMAGE_MAX_BYTES + 1
                ),
            ),
        )

    assert (
        captured.value.status_code
        == status.HTTP_413_CONTENT_TOO_LARGE
    )
    assert (
        captured.value.code
        == "MEDIA_FILE_TOO_LARGE"
    )


def test_upload_rejects_unsupported_content_type() -> None:
    context = make_service()

    with pytest.raises(AppException) as captured:
        context.service.create_upload_url(
            user_id=USER_ID,
            request=MediaUploadUrlRequest(
                purpose=MediaPurpose.ATTENDANCE_LOG,
                file_name="file.exe",
                content_type=(
                    "application/octet-stream"
                ),
                file_size_bytes=1024,
                attendance_log_id="log_001",
                log_entry_id="entry_001",
            ),
        )

    assert (
        captured.value.code
        == "MEDIA_CONTENT_TYPE_UNSUPPORTED"
    )


def test_complete_profile_upload_updates_user() -> None:
    bucket = Mock()
    blob = Mock()

    bucket.blob.return_value = blob

    blob.content_type = "image/jpeg"
    blob.size = 2048
    blob.generate_signed_url.return_value = (
        "https://storage.example/read"
    )

    attendance_repository = Mock()
    entry_repository = Mock()
    user_repository = Mock()

    user_repository.get_by_id.return_value = (
        SimpleNamespace(
            profile_image_storage_path=None,
        )
    )
    user_repository.update_fields.return_value = True

    service = StorageService(
        bucket=bucket,
        attendance_log_repository=(
            attendance_repository
        ),
        log_entry_repository=entry_repository,
        user_repository=user_repository,
    )

    from app.schemas.media import (
        MediaCompleteRequest,
    )

    result = service.complete_upload(
        user_id=USER_ID,
        request=MediaCompleteRequest(
            purpose=MediaPurpose.PROFILE_IMAGE,
            storage_path=(
                f"users/{USER_ID}/profile/"
                "media_001.jpg"
            ),
            content_type="image/jpeg",
        ),
    )

    blob.reload.assert_called_once_with()

    assert result.media_url == (
        "https://storage.example/read"
    )
    assert result.log_media_id is None

    fields = (
        user_repository.update_fields
        .call_args.args[1]
    )

    assert fields[
        "profileImageStoragePath"
    ].endswith("media_001.jpg")

    assert fields["profileImageUrl"] is None


def test_complete_attendance_upload_creates_media() -> None:
    bucket = Mock()
    blob = Mock()

    bucket.blob.return_value = blob

    blob.content_type = "image/webp"
    blob.size = 4096
    blob.generate_signed_url.return_value = (
        "https://storage.example/read"
    )

    attendance_repository = Mock()
    attendance_repository.get_by_id.return_value = (
        SimpleNamespace(
            user_id=USER_ID,
        )
    )

    entry_repository = Mock()
    entry_repository.get_by_id.return_value = (
        SimpleNamespace(
            log_entry_id="entry_001",
        )
    )

    media_repository = Mock()
    media_repository.get_by_storage_path.return_value = None

    media_repository.create.side_effect = (
        lambda log_id, entry_id, media: (
            SimpleNamespace(
                log_media_id="media_doc_001",
                sequence_no=media.sequence_no,
            )
        )
    )

    service = StorageService(
        bucket=bucket,
        attendance_log_repository=(
            attendance_repository
        ),
        log_entry_repository=entry_repository,
        log_media_repository=media_repository,
    )

    from app.schemas.media import (
        MediaCompleteRequest,
    )

    storage_path = (
        f"users/{USER_ID}/attendance-logs/"
        "log_001/entry_001/media_001.webp"
    )

    result = service.complete_upload(
        user_id=USER_ID,
        request=MediaCompleteRequest(
            purpose=MediaPurpose.ATTENDANCE_LOG,
            storage_path=storage_path,
            content_type="image/webp",
            attendance_log_id="log_001",
            log_entry_id="entry_001",
            sequence_no=1,
        ),
    )

    assert result.log_media_id == (
        "media_doc_001"
    )
    assert result.sequence_no == 1

    created = (
        media_repository.create
        .call_args.args[2]
    )

    assert created.storage_path == (
        storage_path
    )
    assert created.media_type.value == "IMAGE"
    assert created.content_type == "image/webp"


def test_complete_upload_rejects_other_user_storage_path() -> None:
    context = make_service()

    from app.schemas.media import (
        MediaCompleteRequest,
    )

    with pytest.raises(AppException) as captured:
        context.service.complete_upload(
            user_id=USER_ID,
            request=MediaCompleteRequest(
                purpose=MediaPurpose.PROFILE_IMAGE,
                storage_path=(
                    "users/another-user/profile/"
                    "media_001.jpg"
                ),
                content_type="image/jpeg",
            ),
        )

    assert (
        captured.value.status_code
        == status.HTTP_403_FORBIDDEN
    )

    assert (
        captured.value.code
        == "MEDIA_STORAGE_PATH_ACCESS_DENIED"
    )


def test_complete_upload_rejects_content_type_mismatch() -> None:
    bucket = Mock()
    blob = Mock()

    bucket.blob.return_value = blob

    blob.content_type = "image/png"
    blob.size = 1024

    attendance_repository = Mock()
    entry_repository = Mock()

    service = StorageService(
        bucket=bucket,
        attendance_log_repository=(
            attendance_repository
        ),
        log_entry_repository=entry_repository,
    )

    from app.schemas.media import (
        MediaCompleteRequest,
    )

    with pytest.raises(AppException) as captured:
        service.complete_upload(
            user_id=USER_ID,
            request=MediaCompleteRequest(
                purpose=MediaPurpose.PROFILE_IMAGE,
                storage_path=(
                    f"users/{USER_ID}/profile/"
                    "media_001.jpg"
                ),
                content_type="image/jpeg",
            ),
        )

    assert (
        captured.value.code
        == "MEDIA_CONTENT_TYPE_MISMATCH"
    )

    blob.delete.assert_called_once_with()


def test_delete_storage_path() -> None:
    bucket = Mock()
    blob = Mock()

    bucket.blob.return_value = blob

    context = make_service()
    context.service._bucket = bucket

    result = context.service.delete_storage_path(
        (
            "users/firebase-user-123/"
            "profile/media_001.jpg"
        )
    )

    assert result is True

    bucket.blob.assert_called_once_with(
        (
            "users/firebase-user-123/"
            "profile/media_001.jpg"
        )
    )

    blob.delete.assert_called_once_with()


def test_delete_user_files_uses_user_prefix() -> None:
    bucket = Mock()

    blob_1 = Mock()
    blob_2 = Mock()

    bucket.list_blobs.return_value = [
        blob_1,
        blob_2,
    ]

    context = make_service()
    context.service._bucket = bucket

    result = context.service.delete_user_files(
        USER_ID
    )

    assert result == 2

    bucket.list_blobs.assert_called_once_with(
        prefix=f"users/{USER_ID}/"
    )

    blob_1.delete.assert_called_once_with()
    blob_2.delete.assert_called_once_with()


def test_complete_upload_deletes_incomplete_blob() -> None:
    context = make_service()

    context.blob.content_type = "image/jpeg"
    context.blob.size = 0

    from app.schemas.media import (
        MediaCompleteRequest,
    )

    with pytest.raises(AppException) as captured:
        context.service.complete_upload(
            user_id=USER_ID,
            request=MediaCompleteRequest(
                purpose=MediaPurpose.PROFILE_IMAGE,
                storage_path=(
                    f"users/{USER_ID}/profile/"
                    "media_incomplete.jpg"
                ),
                content_type="image/jpeg",
            ),
        )

    assert (
        captured.value.code
        == "MEDIA_UPLOAD_INCOMPLETE"
    )

    context.blob.delete.assert_called_once_with()


def test_complete_upload_deletes_actual_oversized_blob() -> None:
    context = make_service()

    context.blob.content_type = "image/jpeg"
    context.blob.size = (
        PROFILE_IMAGE_MAX_BYTES + 1
    )

    from app.schemas.media import (
        MediaCompleteRequest,
    )

    with pytest.raises(AppException) as captured:
        context.service.complete_upload(
            user_id=USER_ID,
            request=MediaCompleteRequest(
                purpose=MediaPurpose.PROFILE_IMAGE,
                storage_path=(
                    f"users/{USER_ID}/profile/"
                    "media_oversized.jpg"
                ),
                content_type="image/jpeg",
            ),
        )

    assert (
        captured.value.status_code
        == status.HTTP_413_CONTENT_TOO_LARGE
    )

    assert (
        captured.value.code
        == "MEDIA_FILE_TOO_LARGE"
    )

    context.blob.delete.assert_called_once_with()

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.core.exceptions import AppException
from app.schemas.media import MediaCompleteRequest, MediaPurpose
from app.services.storage_service import StorageService


USER_ID = "firebase-user-123"
TRIP_ID = "trip_001"
PREFIX = f"users/{USER_ID}/trips/{TRIP_ID}/cover/"
NEW_PATH = PREFIX + "media_new.jpg"
OLD_PATH = PREFIX + "media_old.jpg"


def make_context(*, owner=USER_ID, old_path=None):
    bucket = Mock()
    new_blob = Mock()
    old_blob = Mock()

    new_blob.content_type = "image/jpeg"
    new_blob.size = 2048
    new_blob.generate_signed_url.return_value = (
        "https://storage.example/read"
    )

    def get_blob(path):
        if path == OLD_PATH:
            return old_blob
        return new_blob

    bucket.blob.side_effect = get_blob

    trip_repository = Mock()
    trip_repository.get_by_id.return_value = SimpleNamespace(
        user_id=owner,
        cover_image_storage_path=old_path,
    )
    trip_repository.replace_cover_image.return_value = (
        SimpleNamespace(
            cover_image_storage_path=NEW_PATH,
        ),
        old_path,
    )

    session_repository = Mock()
    session_repository.get_by_storage_path.return_value = {
        "userId": USER_ID,
        "tripId": TRIP_ID,
        "storagePath": NEW_PATH,
        "expectedCoverImageStoragePath": old_path,
        "contentType": "image/jpeg",
        "expiresAt": datetime.now(timezone.utc) + timedelta(hours=1),
    }

    service = StorageService(
        bucket=bucket,
        attendance_log_repository=Mock(),
        log_entry_repository=Mock(),
        trip_repository=trip_repository,
        media_upload_session_repository=session_repository,
    )

    return SimpleNamespace(
        service=service,
        repository=trip_repository,
        session_repository=session_repository,
        new_blob=new_blob,
        old_blob=old_blob,
    )


def complete_request(
    path=NEW_PATH,
    expected_path=None,
):
    return MediaCompleteRequest(
        purpose=MediaPurpose.TRIP_COVER_IMAGE,
        trip_id=TRIP_ID,
        storage_path=path,
        expected_cover_image_storage_path=expected_path,
        content_type="image/jpeg",
    )




def test_complete_trip_cover_saves_storage_path():
    context = make_context()

    result = context.service.complete_upload(
        user_id=USER_ID,
        request=complete_request(),
    )

    assert result.purpose == MediaPurpose.TRIP_COVER_IMAGE
    assert result.storage_path == NEW_PATH
    assert result.media_url == "https://storage.example/read"
    assert result.log_media_id is None
    assert result.sequence_no is None

    context.repository.replace_cover_image.assert_called_once()
    kwargs = context.repository.replace_cover_image.call_args.kwargs
    assert kwargs["trip_id"] == TRIP_ID
    assert kwargs["user_id"] == USER_ID
    assert kwargs["expected_storage_path"] is None
    assert kwargs["storage_path"] == NEW_PATH
    assert "updated_at" in kwargs
    context.old_blob.delete.assert_not_called()



def test_complete_trip_cover_replaces_old_image():
    context = make_context(old_path=OLD_PATH)

    context.service.complete_upload(
        user_id=USER_ID,
        request=complete_request(expected_path=OLD_PATH),
    )

    context.repository.replace_cover_image.assert_called_once()
    kwargs = context.repository.replace_cover_image.call_args.kwargs
    assert kwargs["expected_storage_path"] == OLD_PATH
    assert kwargs["storage_path"] == NEW_PATH
    context.old_blob.delete.assert_not_called()
    context.new_blob.delete.assert_not_called()



def test_complete_trip_cover_rejects_other_owner():
    context = make_context(owner="another-user")

    with pytest.raises(AppException) as captured:
        context.service.complete_upload(
            user_id=USER_ID,
            request=complete_request(),
        )

    assert captured.value.code == "TRIP_ACCESS_DENIED"
    context.repository.replace_cover_image.assert_not_called()
    context.new_blob.reload.assert_not_called()



def test_complete_trip_cover_rejects_wrong_trip_path():
    context = make_context()

    with pytest.raises(AppException) as captured:
        context.service.complete_upload(
            user_id=USER_ID,
            request=complete_request(
                f"users/{USER_ID}/trips/trip_other/cover/media_new.jpg"
            ),
        )

    assert captured.value.code == "MEDIA_STORAGE_PATH_ACCESS_DENIED"
    context.repository.replace_cover_image.assert_not_called()
    context.new_blob.reload.assert_not_called()



def test_complete_trip_cover_does_not_delete_old_on_update_failure():
    context = make_context(old_path=OLD_PATH)
    context.repository.replace_cover_image.return_value = None

    with pytest.raises(AppException) as captured:
        context.service.complete_upload(
            user_id=USER_ID,
            request=complete_request(expected_path=OLD_PATH),
        )

    assert captured.value.code == "TRIP_NOT_FOUND"
    context.repository.replace_cover_image.assert_called_once()
    context.old_blob.delete.assert_not_called()
    context.new_blob.delete.assert_not_called()



def test_complete_trip_cover_maps_repository_conflict():
    from app.repositories.trip_repository import (
        TripCoverImageConflictError,
    )

    context = make_context(old_path=OLD_PATH)
    context.repository.replace_cover_image.side_effect = (
        TripCoverImageConflictError()
    )

    with pytest.raises(AppException) as captured:
        context.service.complete_upload(
            user_id=USER_ID,
            request=complete_request(expected_path=OLD_PATH),
        )

    assert captured.value.status_code == 409
    assert captured.value.code == "TRIP_COVER_IMAGE_CONFLICT"
    context.repository.replace_cover_image.assert_called_once()
    context.old_blob.delete.assert_not_called()
    context.new_blob.delete.assert_not_called()


def test_complete_trip_cover_maps_transaction_access_denied():
    from app.repositories.trip_repository import (
        TripCoverImageAccessDeniedError,
    )

    context = make_context()
    context.repository.replace_cover_image.side_effect = (
        TripCoverImageAccessDeniedError()
    )

    with pytest.raises(AppException) as captured:
        context.service.complete_upload(
            user_id=USER_ID,
            request=complete_request(),
        )

    assert captured.value.status_code == 403
    assert captured.value.code == "TRIP_ACCESS_DENIED"
    context.repository.replace_cover_image.assert_called_once()
    context.new_blob.delete.assert_not_called()


def test_complete_trip_cover_same_path_retry():
    context = make_context(old_path=NEW_PATH)
    context.session_repository.get_by_storage_path.return_value[
        "expectedCoverImageStoragePath"
    ] = None
    context.repository.replace_cover_image.return_value = (
        SimpleNamespace(cover_image_storage_path=NEW_PATH),
        None,
    )

    result = context.service.complete_upload(
        user_id=USER_ID,
        request=complete_request(),
    )

    assert result.storage_path == NEW_PATH
    kwargs = context.repository.replace_cover_image.call_args.kwargs
    assert kwargs["expected_storage_path"] is None
    assert kwargs["storage_path"] == NEW_PATH
    context.old_blob.delete.assert_not_called()
    context.new_blob.delete.assert_not_called()


def test_replace_cover_image_rechecks_owner_inside_transaction():
    from unittest.mock import patch

    from app.repositories.trip_repository import (
        TripCoverImageAccessDeniedError,
        TripRepository,
    )
    from app.schemas.trip import TripRecord

    client = Mock()
    document = client.collection.return_value.document.return_value
    transaction = client.transaction.return_value

    snapshot = Mock()
    snapshot.exists = True
    snapshot.id = TRIP_ID
    snapshot.to_dict.return_value = {}
    document.get.return_value = snapshot

    repository = TripRepository(client=client)
    repository._to_record = Mock(
        return_value=TripRecord.model_construct(
            trip_id=TRIP_ID,
            user_id="another-user",
            cover_image_storage_path=OLD_PATH,
        )
    )

    # Firestore 연결 없이 트랜잭션 본문만 실행합니다.
    with patch(
        "app.repositories.trip_repository.transactional",
        lambda function: function,
    ):
        with pytest.raises(TripCoverImageAccessDeniedError):
            repository.replace_cover_image(
                trip_id=TRIP_ID,
                user_id=USER_ID,
                expected_storage_path=OLD_PATH,
                storage_path=NEW_PATH,
                updated_at=__import__("datetime").datetime.now(
                    __import__("datetime").timezone.utc
                ),
            )

    document.get.assert_called_once_with(
        transaction=transaction,
    )
    transaction.update.assert_not_called()


def test_complete_trip_cover_rejects_expired_session():
    context = make_context()
    context.session_repository.get_by_storage_path.return_value[
        "expiresAt"
    ] = datetime.now(timezone.utc) - timedelta(seconds=1)

    with pytest.raises(AppException) as captured:
        context.service.complete_upload(
            user_id=USER_ID,
            request=complete_request(),
        )

    assert captured.value.status_code == 410
    assert captured.value.code == "MEDIA_UPLOAD_SESSION_EXPIRED"
    context.repository.replace_cover_image.assert_not_called()


def test_complete_trip_cover_rejects_tampered_expected_path():
    context = make_context(old_path=OLD_PATH)

    with pytest.raises(AppException) as captured:
        context.service.complete_upload(
            user_id=USER_ID,
            request=complete_request(expected_path=NEW_PATH),
        )

    assert captured.value.status_code == 409
    assert captured.value.code == "MEDIA_UPLOAD_SESSION_MISMATCH"
    context.repository.replace_cover_image.assert_not_called()


def test_complete_trip_cover_rejects_other_user_session():
    context = make_context()
    context.session_repository.get_by_storage_path.return_value[
        "userId"
    ] = "another-user"

    with pytest.raises(AppException) as captured:
        context.service.complete_upload(
            user_id=USER_ID,
            request=complete_request(),
        )

    assert captured.value.status_code == 403
    assert captured.value.code == "MEDIA_UPLOAD_SESSION_ACCESS_DENIED"
    context.repository.replace_cover_image.assert_not_called()


def test_complete_trip_cover_uses_issued_expected_path():
    from app.repositories.trip_repository import (
        TripCoverImageConflictError,
    )

    context = make_context(old_path=OLD_PATH)
    context.repository.get_by_id.return_value = SimpleNamespace(
        user_id=USER_ID,
        cover_image_storage_path=NEW_PATH,
    )
    context.repository.replace_cover_image.side_effect = (
        TripCoverImageConflictError()
    )

    with pytest.raises(AppException) as captured:
        context.service.complete_upload(
            user_id=USER_ID,
            request=complete_request(expected_path=OLD_PATH),
        )

    assert captured.value.code == "TRIP_COVER_IMAGE_CONFLICT"
    kwargs = context.repository.replace_cover_image.call_args.kwargs
    assert kwargs["expected_storage_path"] == OLD_PATH
    assert kwargs["storage_path"] == NEW_PATH


def test_replace_cover_image_updates_when_expected_path_matches():
    from unittest.mock import patch

    from app.repositories.trip_repository import TripRepository
    from app.schemas.trip import TripRecord

    client = Mock()
    document = client.collection.return_value.document.return_value
    transaction = client.transaction.return_value

    snapshot = Mock()
    snapshot.exists = True
    snapshot.id = TRIP_ID
    snapshot.to_dict.return_value = {}
    document.get.return_value = snapshot

    repository = TripRepository(client=client)
    repository._to_record = Mock(
        return_value=TripRecord.model_construct(
            trip_id=TRIP_ID,
            user_id=USER_ID,
            cover_image_storage_path=OLD_PATH,
        )
    )

    with patch(
        "app.repositories.trip_repository.transactional",
        lambda function: function,
    ):
        result = repository.replace_cover_image(
            trip_id=TRIP_ID,
            user_id=USER_ID,
            expected_storage_path=OLD_PATH,
            storage_path=NEW_PATH,
            updated_at=datetime.now(timezone.utc),
        )

    assert result is not None
    updated, previous_path = result
    assert updated.cover_image_storage_path == NEW_PATH
    assert previous_path == OLD_PATH

    transaction.update.assert_called_once()
    args = transaction.update.call_args.args
    assert args[0] == document
    assert args[1]["coverImageStoragePath"] == NEW_PATH


def test_replace_cover_image_rejects_stale_expected_path():
    from unittest.mock import patch

    from app.repositories.trip_repository import (
        TripCoverImageConflictError,
        TripRepository,
    )
    from app.schemas.trip import TripRecord

    client = Mock()
    document = client.collection.return_value.document.return_value

    snapshot = Mock()
    snapshot.exists = True
    snapshot.id = TRIP_ID
    snapshot.to_dict.return_value = {}
    document.get.return_value = snapshot

    repository = TripRepository(client=client)
    repository._to_record = Mock(
        return_value=TripRecord.model_construct(
            trip_id=TRIP_ID,
            user_id=USER_ID,
            cover_image_storage_path=NEW_PATH,
        )
    )

    with patch(
        "app.repositories.trip_repository.transactional",
        lambda function: function,
    ):
        with pytest.raises(TripCoverImageConflictError):
            repository.replace_cover_image(
                trip_id=TRIP_ID,
                user_id=USER_ID,
                expected_storage_path=OLD_PATH,
                storage_path=OLD_PATH,
                updated_at=datetime.now(timezone.utc),
            )

    client.transaction.return_value.update.assert_not_called()


def test_replace_cover_image_same_path_is_noop():
    from unittest.mock import patch

    from app.repositories.trip_repository import TripRepository
    from app.schemas.trip import TripRecord

    client = Mock()
    document = client.collection.return_value.document.return_value

    snapshot = Mock()
    snapshot.exists = True
    snapshot.id = TRIP_ID
    snapshot.to_dict.return_value = {}
    document.get.return_value = snapshot

    repository = TripRepository(client=client)
    repository._to_record = Mock(
        return_value=TripRecord.model_construct(
            trip_id=TRIP_ID,
            user_id=USER_ID,
            cover_image_storage_path=NEW_PATH,
        )
    )

    with patch(
        "app.repositories.trip_repository.transactional",
        lambda function: function,
    ):
        result = repository.replace_cover_image(
            trip_id=TRIP_ID,
            user_id=USER_ID,
            expected_storage_path=OLD_PATH,
            storage_path=NEW_PATH,
            updated_at=datetime.now(timezone.utc),
        )

    assert result is not None
    updated, previous_path = result
    assert updated.cover_image_storage_path == NEW_PATH
    assert previous_path is None
    client.transaction.return_value.update.assert_not_called()

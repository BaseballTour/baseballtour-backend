from datetime import (
    datetime,
    timedelta,
    timezone,
)

from fastapi import status
from firebase_admin import storage
from google.api_core.exceptions import NotFound
from google.cloud.storage.bucket import Bucket

from app.core.exceptions import AppException
from app.core.firebase import initialize_firebase
from app.core.ids import new_prefixed_id
from app.repositories.attendance_log_repository import (
    AttendanceLogRepository,
)
from app.repositories.log_entry_repository import (
    LogEntryRepository,
)
from app.repositories.log_media_repository import (
    LogMediaRepository,
)
from app.repositories.user_repository import (
    UserRepository,
)
from app.schemas.attendance_log import (
    LogMediaDocument,
    LogMediaType,
)
from app.schemas.media import (
    MediaCompleteRequest,
    MediaCompleteResponse,
    MediaPurpose,
    MediaUploadUrlRequest,
    MediaUploadUrlResponse,
)


UPLOAD_URL_EXPIRATION_SECONDS = 15 * 60
DOWNLOAD_URL_EXPIRATION_SECONDS = 60 * 60

PROFILE_IMAGE_MAX_BYTES = 10 * 1024 * 1024
ATTENDANCE_IMAGE_MAX_BYTES = 15 * 1024 * 1024
ATTENDANCE_VIDEO_MAX_BYTES = 200 * 1024 * 1024


CONTENT_TYPE_EXTENSIONS = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
}

PROFILE_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}

ATTENDANCE_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}

ATTENDANCE_VIDEO_CONTENT_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/webm",
}


class StorageService:
    """Firebase Storage 미디어 업로드를 담당합니다."""

    def __init__(
        self,
        bucket: Bucket | None = None,
        attendance_log_repository: (
            AttendanceLogRepository | None
        ) = None,
        log_entry_repository: (
            LogEntryRepository | None
        ) = None,
        log_media_repository: (
            LogMediaRepository | None
        ) = None,
        user_repository: (
            UserRepository | None
        ) = None,
    ) -> None:
        self._bucket = (
            bucket
            or storage.bucket(
                app=initialize_firebase()
            )
        )

        self._attendance_log_repository = (
            attendance_log_repository
            or AttendanceLogRepository()
        )

        self._log_entry_repository = (
            log_entry_repository
            or LogEntryRepository()
        )

        # complete API에서만 필요하므로
        # 테스트 시 실제 Firestore 생성 방지를 위해 lazy 처리합니다.
        self._log_media_repository = (
            log_media_repository
        )

        self._user_repository = (
            user_repository
        )

    def _get_log_media_repository(
        self,
    ) -> LogMediaRepository:
        if self._log_media_repository is None:
            self._log_media_repository = (
                LogMediaRepository()
            )

        return self._log_media_repository

    def _get_user_repository(
        self,
    ) -> UserRepository:
        if self._user_repository is None:
            self._user_repository = (
                UserRepository()
            )

        return self._user_repository

    def create_upload_url(
        self,
        *,
        user_id: str,
        request: MediaUploadUrlRequest,
    ) -> MediaUploadUrlResponse:
        """용도와 소유권을 검증하고 PUT signed URL을 생성합니다."""

        self._validate_file(
            purpose=request.purpose,
            content_type=request.content_type,
            file_size_bytes=request.file_size_bytes,
        )

        if (
            request.purpose
            == MediaPurpose.ATTENDANCE_LOG
        ):
            self._validate_attendance_target(
                user_id=user_id,
                attendance_log_id=(
                    request.attendance_log_id
                ),
                log_entry_id=(
                    request.log_entry_id
                ),
            )

        storage_path = self._build_storage_path(
            user_id=user_id,
            request=request,
        )

        blob = self._bucket.blob(
            storage_path
        )

        try:
            upload_url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(
                    seconds=(
                        UPLOAD_URL_EXPIRATION_SECONDS
                    )
                ),
                method="PUT",
                content_type=request.content_type,
            )

        except Exception as exc:
            raise AppException(
                status_code=(
                    status.HTTP_503_SERVICE_UNAVAILABLE
                ),
                code="STORAGE_UNAVAILABLE",
                message=(
                    "미디어 업로드 URL을 "
                    "생성할 수 없습니다."
                ),
            ) from exc

        return MediaUploadUrlResponse(
            upload_url=upload_url,
            storage_path=storage_path,
            content_type=request.content_type,
            expires_in_seconds=(
                UPLOAD_URL_EXPIRATION_SECONDS
            ),
            required_headers={
                "Content-Type": request.content_type,
            },
        )

    def complete_upload(
        self,
        *,
        user_id: str,
        request: MediaCompleteRequest,
    ) -> MediaCompleteResponse:
        """실제 Storage 객체를 검증하고 서비스 데이터에 연결합니다."""

        self._validate_owned_storage_path(
            user_id=user_id,
            request=request,
        )

        if (
            request.purpose
            == MediaPurpose.ATTENDANCE_LOG
        ):
            self._validate_attendance_target(
                user_id=user_id,
                attendance_log_id=(
                    request.attendance_log_id
                ),
                log_entry_id=(
                    request.log_entry_id
                ),
            )

        blob = self._bucket.blob(
            request.storage_path
        )

        try:
            blob.reload()

        except NotFound as exc:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="MEDIA_UPLOAD_NOT_FOUND",
                message=(
                    "업로드된 미디어 파일을 "
                    "찾을 수 없습니다."
                ),
            ) from exc

        except Exception as exc:
            raise AppException(
                status_code=(
                    status.HTTP_503_SERVICE_UNAVAILABLE
                ),
                code="STORAGE_UNAVAILABLE",
                message=(
                    "업로드된 미디어 파일을 "
                    "확인할 수 없습니다."
                ),
            ) from exc

        actual_content_type = (
            str(blob.content_type or "")
            .strip()
            .lower()
        )

        if (
            actual_content_type
            != request.content_type
        ):
            self._delete_blob_best_effort(
                blob
            )

            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="MEDIA_CONTENT_TYPE_MISMATCH",
                message=(
                    "업로드된 파일의 형식이 "
                    "요청 정보와 일치하지 않습니다."
                ),
            )

        actual_size = blob.size

        if (
            actual_size is None
            or actual_size <= 0
        ):
            self._delete_blob_best_effort(
                blob
            )
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="MEDIA_UPLOAD_INCOMPLETE",
                message=(
                    "업로드된 파일 정보를 "
                    "확인할 수 없습니다."
                ),
            )

        try:
            self._validate_file(
                purpose=request.purpose,
                content_type=actual_content_type,
                file_size_bytes=actual_size,
            )
        except AppException:
            # signed PUT 단계의 fileSizeBytes는
            # 클라이언트가 보낸 예상값이므로 complete 시
            # 실제 Storage 객체를 다시 검증합니다.
            # 실제 객체가 정책을 위반하면 orphan blob을
            # 남기지 않고 best-effort로 정리합니다.
            self._delete_blob_best_effort(
                blob
            )
            raise

        expected_extension = (
            CONTENT_TYPE_EXTENSIONS[
                actual_content_type
            ]
        )

        if not request.storage_path.endswith(
            expected_extension
        ):
            self._delete_blob_best_effort(
                blob
            )

            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="MEDIA_EXTENSION_MISMATCH",
                message=(
                    "Storage 경로와 실제 "
                    "미디어 형식이 일치하지 않습니다."
                ),
            )

        log_media_id = None
        sequence_no = None

        if (
            request.purpose
            == MediaPurpose.PROFILE_IMAGE
        ):
            self._complete_profile_image(
                user_id=user_id,
                storage_path=request.storage_path,
            )

        else:
            media_record = (
                self._complete_attendance_media(
                    request=request,
                    content_type=actual_content_type,
                )
            )

            log_media_id = (
                media_record.log_media_id
            )

            sequence_no = (
                media_record.sequence_no
            )

        media_url = self.create_download_url(
            request.storage_path
        )

        return MediaCompleteResponse(
            purpose=request.purpose,
            storage_path=request.storage_path,
            content_type=actual_content_type,
            media_url=media_url,
            log_media_id=log_media_id,
            sequence_no=sequence_no,
        )

    def delete_storage_path(
        self,
        storage_path: str,
    ) -> bool:
        """Storage 객체를 삭제합니다.

        이미 없는 객체는 정상적으로 정리된 것으로 취급합니다.
        """

        blob = self._bucket.blob(
            storage_path
        )

        try:
            blob.delete()

        except NotFound:
            return False

        except Exception as exc:
            raise AppException(
                status_code=(
                    status.HTTP_503_SERVICE_UNAVAILABLE
                ),
                code="STORAGE_UNAVAILABLE",
                message=(
                    "미디어 파일을 삭제할 수 없습니다."
                ),
            ) from exc

        return True

    def delete_user_files(
        self,
        user_id: str,
    ) -> int:
        """사용자의 Storage 객체를 모두 삭제합니다."""

        prefix = f"users/{user_id}/"
        deleted_count = 0

        try:
            blobs = self._bucket.list_blobs(
                prefix=prefix
            )

            for blob in blobs:
                blob.delete()
                deleted_count += 1

        except Exception as exc:
            raise AppException(
                status_code=(
                    status.HTTP_503_SERVICE_UNAVAILABLE
                ),
                code="STORAGE_UNAVAILABLE",
                message=(
                    "사용자 미디어 파일을 "
                    "정리할 수 없습니다."
                ),
            ) from exc

        return deleted_count

    def create_download_url(
        self,
        storage_path: str,
    ) -> str:
        """Storage 객체의 임시 GET signed URL을 생성합니다."""

        blob = self._bucket.blob(
            storage_path
        )

        try:
            return blob.generate_signed_url(
                version="v4",
                expiration=timedelta(
                    seconds=(
                        DOWNLOAD_URL_EXPIRATION_SECONDS
                    )
                ),
                method="GET",
            )

        except Exception as exc:
            raise AppException(
                status_code=(
                    status.HTTP_503_SERVICE_UNAVAILABLE
                ),
                code="STORAGE_UNAVAILABLE",
                message=(
                    "미디어 조회 URL을 "
                    "생성할 수 없습니다."
                ),
            ) from exc

    def _complete_profile_image(
        self,
        *,
        user_id: str,
        storage_path: str,
    ) -> None:
        repository = (
            self._get_user_repository()
        )

        user = repository.get_by_id(
            user_id
        )

        if user is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="USER_NOT_FOUND",
                message=(
                    "사용자 정보를 찾을 수 없습니다."
                ),
            )

        old_storage_path = (
            user.profile_image_storage_path
        )

        updated = repository.update_fields(
            user_id,
            {
                "profileImageStoragePath": (
                    storage_path
                ),
                # 기존 외부 URL보다 Storage 경로를
                # 기준 데이터로 사용합니다.
                "profileImageUrl": None,
                "updatedAt": datetime.now(
                    timezone.utc
                ),
            },
        )

        if not updated:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="USER_NOT_FOUND",
                message=(
                    "사용자 정보를 찾을 수 없습니다."
                ),
            )

        if (
            old_storage_path
            and old_storage_path
            != storage_path
        ):
            old_blob = self._bucket.blob(
                old_storage_path
            )

            self._delete_blob_best_effort(
                old_blob
            )

    def _complete_attendance_media(
        self,
        *,
        request: MediaCompleteRequest,
        content_type: str,
    ):
        attendance_log_id = (
            request.attendance_log_id
        )
        log_entry_id = (
            request.log_entry_id
        )
        sequence_no = request.sequence_no

        if (
            attendance_log_id is None
            or log_entry_id is None
            or sequence_no is None
        ):
            raise RuntimeError(
                "직관 로그 미디어 대상 정보가 없습니다."
            )

        repository = (
            self._get_log_media_repository()
        )

        existing = (
            repository.get_by_storage_path(
                attendance_log_id,
                log_entry_id,
                request.storage_path,
            )
        )

        if existing is not None:
            return existing

        media_type = (
            LogMediaType.IMAGE
            if content_type.startswith(
                "image/"
            )
            else LogMediaType.VIDEO
        )

        document = LogMediaDocument(
            media_type=media_type,
            storage_path=request.storage_path,
            content_type=content_type,
            media_url=None,
            thumbnail_url=None,
            sequence_no=sequence_no,
            created_at=datetime.now(
                timezone.utc
            ),
        )

        return repository.create(
            attendance_log_id,
            log_entry_id,
            document,
        )

    def _validate_attendance_target(
        self,
        *,
        user_id: str,
        attendance_log_id: str | None,
        log_entry_id: str | None,
    ) -> None:
        if (
            attendance_log_id is None
            or log_entry_id is None
        ):
            raise RuntimeError(
                "직관 로그 미디어 대상 ID가 없습니다."
            )

        attendance_log = (
            self._attendance_log_repository
            .get_by_id(attendance_log_id)
        )

        if attendance_log is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="ATTENDANCE_LOG_NOT_FOUND",
                message=(
                    "직관 로그를 찾을 수 없습니다."
                ),
            )

        if attendance_log.user_id != user_id:
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="ATTENDANCE_LOG_ACCESS_DENIED",
                message=(
                    "해당 직관 로그에 접근할 "
                    "권한이 없습니다."
                ),
            )

        entry = (
            self._log_entry_repository
            .get_by_id(
                attendance_log_id,
                log_entry_id,
            )
        )

        if entry is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="LOG_ENTRY_NOT_FOUND",
                message=(
                    "직관 로그 항목을 "
                    "찾을 수 없습니다."
                ),
            )

    @staticmethod
    def _validate_owned_storage_path(
        *,
        user_id: str,
        request: MediaCompleteRequest,
    ) -> None:
        if (
            request.purpose
            == MediaPurpose.PROFILE_IMAGE
        ):
            expected_prefix = (
                f"users/{user_id}/profile/"
            )

        else:
            expected_prefix = (
                f"users/{user_id}/attendance-logs/"
                f"{request.attendance_log_id}/"
                f"{request.log_entry_id}/"
            )

        if not request.storage_path.startswith(
            expected_prefix
        ):
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="MEDIA_STORAGE_PATH_ACCESS_DENIED",
                message=(
                    "해당 Storage 파일에 접근할 "
                    "권한이 없습니다."
                ),
            )

    @staticmethod
    def _validate_file(
        *,
        purpose: MediaPurpose,
        content_type: str,
        file_size_bytes: int,
    ) -> None:
        if (
            content_type
            not in CONTENT_TYPE_EXTENSIONS
        ):
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="MEDIA_CONTENT_TYPE_UNSUPPORTED",
                message=(
                    "지원하지 않는 미디어 형식입니다."
                ),
            )

        if (
            purpose
            == MediaPurpose.PROFILE_IMAGE
        ):
            if (
                content_type
                not in PROFILE_IMAGE_CONTENT_TYPES
            ):
                raise AppException(
                    status_code=(
                        status.HTTP_400_BAD_REQUEST
                    ),
                    code=(
                        "MEDIA_CONTENT_TYPE_UNSUPPORTED"
                    ),
                    message=(
                        "프로필에는 이미지 파일만 "
                        "업로드할 수 있습니다."
                    ),
                )

            max_bytes = (
                PROFILE_IMAGE_MAX_BYTES
            )

        elif (
            content_type
            in ATTENDANCE_IMAGE_CONTENT_TYPES
        ):
            max_bytes = (
                ATTENDANCE_IMAGE_MAX_BYTES
            )

        elif (
            content_type
            in ATTENDANCE_VIDEO_CONTENT_TYPES
        ):
            max_bytes = (
                ATTENDANCE_VIDEO_MAX_BYTES
            )

        else:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="MEDIA_CONTENT_TYPE_UNSUPPORTED",
                message=(
                    "지원하지 않는 미디어 형식입니다."
                ),
            )

        if file_size_bytes > max_bytes:
            raise AppException(
                status_code=(
                    status.HTTP_413_CONTENT_TOO_LARGE
                ),
                code="MEDIA_FILE_TOO_LARGE",
                message=(
                    "허용된 최대 파일 크기를 "
                    "초과했습니다."
                ),
                details={
                    "maxBytes": max_bytes,
                },
            )

    @staticmethod
    def _delete_blob_best_effort(
        blob,
    ) -> None:
        try:
            blob.delete()
        except Exception:
            # 이전 파일 정리 실패가 신규 업로드 완료를
            # 실패시키지는 않도록 합니다.
            pass

    @staticmethod
    def _build_storage_path(
        *,
        user_id: str,
        request: MediaUploadUrlRequest,
    ) -> str:
        extension = CONTENT_TYPE_EXTENSIONS[
            request.content_type
        ]

        media_id = new_prefixed_id(
            "media"
        )

        if (
            request.purpose
            == MediaPurpose.PROFILE_IMAGE
        ):
            return (
                f"users/{user_id}/profile/"
                f"{media_id}{extension}"
            )

        return (
            f"users/{user_id}/attendance-logs/"
            f"{request.attendance_log_id}/"
            f"{request.log_entry_id}/"
            f"{media_id}{extension}"
        )

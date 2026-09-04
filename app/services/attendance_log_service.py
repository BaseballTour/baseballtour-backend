import base64
import binascii
import json
from datetime import datetime, timezone

from fastapi import status

from app.core.exceptions import AppException
from app.models.itinerary import ItineraryItemType
from app.repositories.attendance_log_repository import (
    AttendanceLogRepository,
)
from app.repositories.game_repository import GameRepository
from app.repositories.itinerary_plan_repository import (
    ItineraryPlanRepository,
)
from app.repositories.log_entry_repository import (
    LogEntryRepository,
)
from app.repositories.log_media_repository import (
    LogMediaRepository,
)
from app.repositories.trip_repository import TripRepository
from app.repositories.user_repository import UserRepository
from app.schemas.attendance_log import (
    AttendanceLogArchiveItemResponse,
    AttendanceLogDetailResponse,
    AttendanceLogDocument,
    AttendanceLogGameResult,
    AttendanceLogHomeSide,
    AttendanceLogRecord,
    AttendanceLogResponse,
    AttendanceLogStatus,
    AttendanceLogUpdateRequest,
    AttendanceLogVisibility,
    LogEntryDocument,
    LogEntryResponse,
    LogEntryType,
    LogEntryUpdateRequest,
    LogMediaResponse,
    LogMediaType,
)
from app.schemas.itinerary_plan import (
    ItineraryPlanRecord,
    ItineraryPlanStatus,
)
from app.schemas.trip import TripRecord
from app.services.attendance_result import (
    resolve_game_result,
    resolve_home_side,
)
from app.services.game_service import GameService
from app.services.storage_service import StorageService


class AttendanceLogService:
    """여행과 확정 일정을 기반으로 직관 로그를 생성합니다."""

    def __init__(
        self,
        trip_repository: TripRepository | None = None,
        game_repository: GameRepository | None = None,
        itinerary_plan_repository: (
            ItineraryPlanRepository | None
        ) = None,
        attendance_log_repository: (
            AttendanceLogRepository | None
        ) = None,
        log_entry_repository: (
            LogEntryRepository | None
        ) = None,
        log_media_repository: (
            LogMediaRepository | None
        ) = None,
        storage_service: (
            StorageService | None
        ) = None,
        user_repository: (
            UserRepository | None
        ) = None,
        game_service: (
            GameService | None
        ) = None,
    ) -> None:
        self._trip_repository = (
            trip_repository
            or TripRepository()
        )
        self._game_repository = (
            game_repository
            or GameRepository()
        )
        self._itinerary_plan_repository = (
            itinerary_plan_repository
            or ItineraryPlanRepository()
        )
        self._attendance_log_repository = (
            attendance_log_repository
            or AttendanceLogRepository()
        )
        self._log_entry_repository = (
            log_entry_repository
            or LogEntryRepository()
        )

        # 기존 create_draft/get_itinerary 테스트에서
        # Firestore/Storage를 불필요하게 초기화하지 않도록
        # 실제 필요 시 생성합니다.
        self._log_media_repository = (
            log_media_repository
        )
        self._storage_service = (
            storage_service
        )
        self._user_repository = (
            user_repository
        )
        self._game_service = (
            game_service
        )

    def create_draft(
        self,
        *,
        user_id: str,
        trip_id: str,
        log_title: str | None = None,
    ) -> AttendanceLogRecord:
        """여행의 현재 확정 일정을 기반으로 DRAFT 로그를 생성합니다."""

        trip = self._get_owned_trip_or_raise(
            user_id=user_id,
            trip_id=trip_id,
        )

        self._validate_duplicate_log(
            trip_id=trip_id,
        )

        plan = self._get_active_plan_or_raise(
            trip=trip,
        )

        self._validate_game_exists(
            game_id=trip.game_id,
        )

        user = self._get_user_repository().get_by_id(
            user_id
        )

        if user is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="USER_NOT_FOUND",
                message="사용자 정보를 찾을 수 없습니다.",
            )

        now = datetime.now(timezone.utc)

        log_document = AttendanceLogDocument(
            user_id=user_id,
            trip_id=trip.trip_id,
            game_id=trip.game_id,
            plan_id=plan.plan_id,
            support_team_id=user.support_team_id,
            log_title=(
                log_title
                if log_title is not None
                else trip.title
            ),
            summary_text=None,
            log_status=AttendanceLogStatus.DRAFT,
            visibility=AttendanceLogVisibility.PRIVATE,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )

        attendance_log = (
            self._attendance_log_repository.create(
                log_document
            )
        )

        self._create_entries(
            attendance_log_id=(
                attendance_log.attendance_log_id
            ),
            plan=plan,
            now=now,
        )

        return attendance_log

    def get_itinerary(
        self,
        *,
        user_id: str,
        attendance_log_id: str,
    ) -> ItineraryPlanRecord:
        """직관 로그 생성 시점의 일정 Plan을 읽기 전용으로 조회합니다."""

        attendance_log = (
            self._attendance_log_repository.get_by_id(
                attendance_log_id
            )
        )

        if attendance_log is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="ATTENDANCE_LOG_NOT_FOUND",
                message="직관 로그를 찾을 수 없습니다.",
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

        if attendance_log.plan_id is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="ITINERARY_PLAN_NOT_FOUND",
                message=(
                    "직관 로그에 연결된 일정 정보를 "
                    "찾을 수 없습니다."
                ),
            )

        plan = self._itinerary_plan_repository.get_by_id(
            attendance_log.plan_id
        )

        if plan is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="ITINERARY_PLAN_NOT_FOUND",
                message=(
                    "직관 로그에 연결된 일정 정보를 "
                    "찾을 수 없습니다."
                ),
            )

        if (
            plan.user_id != user_id
            or plan.trip_id != attendance_log.trip_id
        ):
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="ATTENDANCE_LOG_PLAN_MISMATCH",
                message=(
                    "직관 로그와 일정 정보의 연결이 "
                    "일치하지 않습니다."
                ),
            )

        return plan

    def to_response(
        self,
        record: AttendanceLogRecord,
    ) -> AttendanceLogResponse:
        """직관 로그 Record를 API 응답으로 변환합니다."""

        return self._to_log_response(
            record
        )

    def list_logs(
        self,
        *,
        user_id: str,
    ) -> list[AttendanceLogResponse]:
        """사용자 자신의 직관 로그 목록을 조회합니다."""

        records = (
            self._attendance_log_repository
            .get_by_user_id(user_id)
        )

        return [
            self._to_log_response(record)
            for record in records
        ]

    def list_archive_logs(
        self,
        *,
        user_id: str,
        page_size: int = 12,
        page_token: str | None = None,
    ) -> tuple[
        list[AttendanceLogArchiveItemResponse],
        str | None,
    ]:
        """직관 로그 아카이브 휠용 목록을 반환합니다."""

        user = self._get_user_repository().get_by_id(
            user_id
        )

        if user is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="USER_NOT_FOUND",
                message="사용자 정보를 찾을 수 없습니다.",
            )

        records = (
            self._attendance_log_repository
            .get_by_user_id(user_id)
        )

        cursor = None

        if page_token is not None:
            cursor = self._decode_archive_page_token(
                page_token=page_token,
                user_id=user_id,
            )

        if cursor is not None:
            records = [
                record
                for record in records
                if (
                    record.created_at,
                    record.attendance_log_id,
                )
                < cursor
            ]

        page_records = records[: page_size + 1]

        has_next = len(page_records) > page_size

        if has_next:
            page_records = page_records[:page_size]

        data = [
            self._to_archive_response(
                record=record,
                support_team_id=(
                    record.support_team_id
                    if record.support_team_id is not None
                    else user.support_team_id
                ),
            )
            for record in page_records
        ]

        next_page_token = None

        if has_next and page_records:
            last = page_records[-1]

            next_page_token = (
                self._encode_archive_page_token(
                    user_id=user_id,
                    created_at=last.created_at,
                    attendance_log_id=(
                        last.attendance_log_id
                    ),
                )
            )

        return data, next_page_token

    def get_detail(
        self,
        *,
        user_id: str,
        attendance_log_id: str,
    ) -> AttendanceLogDetailResponse:
        """직관 로그 상세와 Entry/Media를 조회합니다."""

        attendance_log = (
            self._get_readable_log_or_raise(
                user_id=user_id,
                attendance_log_id=attendance_log_id,
            )
        )

        entries = (
            self._log_entry_repository.get_all(
                attendance_log_id
            )
        )

        return AttendanceLogDetailResponse(
            attendance_log_id=(
                attendance_log.attendance_log_id
            ),
            trip_id=attendance_log.trip_id,
            game_id=attendance_log.game_id,
            plan_id=attendance_log.plan_id,
            log_title=attendance_log.log_title,
            summary_text=attendance_log.summary_text,
            seat=attendance_log.seat,
            log_status=attendance_log.log_status,
            visibility=attendance_log.visibility,
            created_at=attendance_log.created_at,
            updated_at=attendance_log.updated_at,
            entries=[
                self._to_entry_response(
                    attendance_log_id=(
                        attendance_log_id
                    ),
                    entry=entry,
                )
                for entry in entries
            ],
        )

    def update_log(
        self,
        *,
        user_id: str,
        attendance_log_id: str,
        request: AttendanceLogUpdateRequest,
    ) -> AttendanceLogResponse:
        """소유자의 직관 로그 기본 정보를 수정합니다."""

        self._get_owned_log_or_raise(
            user_id=user_id,
            attendance_log_id=attendance_log_id,
        )

        if (
            "log_status"
            in request.model_fields_set
            and request.log_status
            == AttendanceLogStatus.ARCHIVED
        ):
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="ATTENDANCE_LOG_STATUS_INVALID",
                message=(
                    "ARCHIVED 상태 변경은 "
                    "직관 로그 삭제 API를 사용해야 합니다."
                ),
            )

        updates = {}

        if "log_title" in request.model_fields_set:
            updates["logTitle"] = (
                request.log_title
            )

        if (
            "summary_text"
            in request.model_fields_set
        ):
            updates["summaryText"] = (
                request.summary_text
            )

        if "seat" in request.model_fields_set:
            updates["seat"] = request.seat

        if (
            "log_status"
            in request.model_fields_set
        ):
            updates["logStatus"] = (
                request.log_status.value
                if request.log_status is not None
                else None
            )

        if (
            "visibility"
            in request.model_fields_set
        ):
            updates["visibility"] = (
                request.visibility.value
                if request.visibility is not None
                else None
            )

        updates["updatedAt"] = datetime.now(
            timezone.utc
        )

        updated = (
            self._attendance_log_repository.update(
                attendance_log_id,
                updates,
            )
        )

        if updated is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="ATTENDANCE_LOG_NOT_FOUND",
                message=(
                    "직관 로그를 찾을 수 없습니다."
                ),
            )

        return self._to_log_response(
            updated
        )

    def update_entry(
        self,
        *,
        user_id: str,
        attendance_log_id: str,
        log_entry_id: str,
        request: LogEntryUpdateRequest,
    ) -> LogEntryResponse:
        """직관 로그 Entry를 수정합니다."""

        self._get_owned_log_or_raise(
            user_id=user_id,
            attendance_log_id=attendance_log_id,
        )

        updates = {}

        if (
            "entry_title"
            in request.model_fields_set
        ):
            updates["entryTitle"] = (
                request.entry_title
            )

        if (
            "review_text"
            in request.model_fields_set
        ):
            updates["reviewText"] = (
                request.review_text
            )

        if (
            "occurred_at"
            in request.model_fields_set
        ):
            updates["occurredAt"] = (
                request.occurred_at
            )

        updates["updatedAt"] = datetime.now(
            timezone.utc
        )

        updated = (
            self._log_entry_repository.update(
                attendance_log_id,
                log_entry_id,
                updates,
            )
        )

        if updated is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="LOG_ENTRY_NOT_FOUND",
                message=(
                    "직관 로그 항목을 찾을 수 없습니다."
                ),
            )

        return self._to_entry_response(
            attendance_log_id=attendance_log_id,
            entry=updated,
        )

    def delete_media(
        self,
        *,
        user_id: str,
        attendance_log_id: str,
        log_entry_id: str,
        log_media_id: str,
    ) -> None:
        """로그 미디어와 Storage 객체를 삭제합니다."""

        self._get_owned_log_or_raise(
            user_id=user_id,
            attendance_log_id=attendance_log_id,
        )

        entry = (
            self._log_entry_repository.get_by_id(
                attendance_log_id,
                log_entry_id,
            )
        )

        if entry is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="LOG_ENTRY_NOT_FOUND",
                message=(
                    "직관 로그 항목을 찾을 수 없습니다."
                ),
            )

        repository = (
            self._get_log_media_repository()
        )

        media = repository.get_by_id(
            attendance_log_id,
            log_entry_id,
            log_media_id,
        )

        if media is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="LOG_MEDIA_NOT_FOUND",
                message=(
                    "직관 로그 미디어를 찾을 수 없습니다."
                ),
            )

        if media.storage_path:
            self._get_storage_service().delete_storage_path(
                media.storage_path
            )

        deleted = repository.delete(
            attendance_log_id,
            log_entry_id,
            log_media_id,
        )

        if not deleted:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="LOG_MEDIA_NOT_FOUND",
                message=(
                    "직관 로그 미디어를 찾을 수 없습니다."
                ),
            )

    def delete_entry(
        self,
        *,
        user_id: str,
        attendance_log_id: str,
        log_entry_id: str,
    ) -> None:
        """Entry와 연결 미디어를 모두 삭제합니다."""

        self._get_owned_log_or_raise(
            user_id=user_id,
            attendance_log_id=attendance_log_id,
        )

        entry = (
            self._log_entry_repository.get_by_id(
                attendance_log_id,
                log_entry_id,
            )
        )

        if entry is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="LOG_ENTRY_NOT_FOUND",
                message=(
                    "직관 로그 항목을 찾을 수 없습니다."
                ),
            )

        self._delete_entry_contents(
            attendance_log_id=attendance_log_id,
            log_entry_id=log_entry_id,
        )

    def delete_log(
        self,
        *,
        user_id: str,
        attendance_log_id: str,
    ) -> None:
        """직관 로그 하위 데이터를 정리하고 soft delete합니다."""

        self._get_owned_log_or_raise(
            user_id=user_id,
            attendance_log_id=attendance_log_id,
        )

        entries = (
            self._log_entry_repository.get_all(
                attendance_log_id
            )
        )

        for entry in entries:
            self._delete_entry_contents(
                attendance_log_id=(
                    attendance_log_id
                ),
                log_entry_id=(
                    entry.log_entry_id
                ),
            )

        deleted_at = datetime.now(
            timezone.utc
        )

        deleted = (
            self._attendance_log_repository
            .soft_delete(
                attendance_log_id,
                deleted_at=deleted_at,
            )
        )

        if not deleted:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="ATTENDANCE_LOG_NOT_FOUND",
                message=(
                    "직관 로그를 찾을 수 없습니다."
                ),
            )

    def _delete_entry_contents(
        self,
        *,
        attendance_log_id: str,
        log_entry_id: str,
    ) -> None:
        repository = (
            self._get_log_media_repository()
        )

        media_items = repository.get_all(
            attendance_log_id,
            log_entry_id,
        )

        for media in media_items:
            if media.storage_path:
                self._get_storage_service().delete_storage_path(
                    media.storage_path
                )

            repository.delete(
                attendance_log_id,
                log_entry_id,
                media.log_media_id,
            )

        deleted = (
            self._log_entry_repository.delete(
                attendance_log_id,
                log_entry_id,
            )
        )

        if not deleted:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="LOG_ENTRY_NOT_FOUND",
                message=(
                    "직관 로그 항목을 찾을 수 없습니다."
                ),
            )

    def _get_readable_log_or_raise(
        self,
        *,
        user_id: str,
        attendance_log_id: str,
    ) -> AttendanceLogRecord:
        """
        소유자 또는 PUBLIC 로그에 대해 상세 조회를 허용합니다.

        수정·삭제·itinerary는 이 메서드를 사용하지 않고
        반드시 _get_owned_log_or_raise를 사용합니다.
        """

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

        if attendance_log.user_id == user_id:
            return attendance_log

        if (
            attendance_log.visibility
            == AttendanceLogVisibility.PUBLIC
        ):
            return attendance_log

        raise AppException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="ATTENDANCE_LOG_ACCESS_DENIED",
            message=(
                "해당 직관 로그에 접근할 "
                "권한이 없습니다."
            ),
        )

    def _get_owned_log_or_raise(
        self,
        *,
        user_id: str,
        attendance_log_id: str,
    ) -> AttendanceLogRecord:
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

        return attendance_log

    def _get_log_media_repository(
        self,
    ) -> LogMediaRepository:
        if self._log_media_repository is None:
            self._log_media_repository = (
                LogMediaRepository()
            )

        return self._log_media_repository

    def _get_storage_service(
        self,
    ) -> StorageService:
        if self._storage_service is None:
            self._storage_service = (
                StorageService()
            )

        return self._storage_service

    @staticmethod
    def _encode_archive_page_token(
        *,
        user_id: str,
        created_at: datetime,
        attendance_log_id: str,
    ) -> str:
        payload = {
            "userId": user_id,
            "createdAt": created_at.isoformat(),
            "attendanceLogId": attendance_log_id,
        }

        encoded = json.dumps(
            payload,
            separators=(",", ":"),
        ).encode("utf-8")

        return base64.urlsafe_b64encode(
            encoded
        ).decode("ascii")

    @staticmethod
    def _decode_archive_page_token(
        *,
        page_token: str,
        user_id: str,
    ) -> tuple[datetime, str]:
        try:
            decoded = base64.urlsafe_b64decode(
                page_token.encode("ascii")
            )

            payload = json.loads(
                decoded.decode("utf-8")
            )

            if payload["userId"] != user_id:
                raise ValueError

            created_at = datetime.fromisoformat(
                payload["createdAt"]
            )

            if created_at.tzinfo is None:
                raise ValueError

            attendance_log_id = payload[
                "attendanceLogId"
            ]

            if (
                not isinstance(attendance_log_id, str)
                or not attendance_log_id
            ):
                raise ValueError

            return (
                created_at,
                attendance_log_id,
            )

        except (
            ValueError,
            KeyError,
            TypeError,
            json.JSONDecodeError,
            binascii.Error,
            UnicodeError,
        ) as exc:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_PAGE_TOKEN",
                message=(
                    "직관 로그 페이지 토큰이 "
                    "올바르지 않습니다."
                ),
            ) from exc

    def _get_user_repository(
        self,
    ) -> UserRepository:
        if self._user_repository is None:
            self._user_repository = UserRepository()

        return self._user_repository

    def _get_game_service(
        self,
    ) -> GameService:
        if self._game_service is None:
            self._game_service = GameService()

        return self._game_service

    def _to_archive_response(
        self,
        *,
        record: AttendanceLogRecord,
        support_team_id: str | None,
    ) -> AttendanceLogArchiveItemResponse:
        game = self._get_game_service().get_game(
            record.game_id
        )

        home_side = self._resolve_home_side(
            support_team_id=support_team_id,
            home_team_id=game.home_team.team_id,
            away_team_id=game.away_team.team_id,
        )

        result = self._resolve_game_result(
            home_side=home_side,
            home_score=game.home_score,
            away_score=game.away_score,
        )

        cover_image_url = self._find_cover_image_url(
            attendance_log_id=(
                record.attendance_log_id
            )
        )

        return AttendanceLogArchiveItemResponse(
            attendance_log_id=(
                record.attendance_log_id
            ),
            trip_id=record.trip_id,
            game_id=record.game_id,
            plan_id=record.plan_id,
            log_title=record.log_title,
            summary_text=record.summary_text,
            seat=record.seat,
            game_start_at=game.game_start_at,
            stadium_name=game.stadium.name,
            home_team_name=game.home_team.name,
            away_team_name=game.away_team.name,
            home_score=game.home_score,
            away_score=game.away_score,
            home_side=home_side,
            result=result,
            cover_image_url=cover_image_url,
            log_status=record.log_status,
            visibility=record.visibility,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    @staticmethod
    def _resolve_home_side(
        *,
        support_team_id: str | None,
        home_team_id: str,
        away_team_id: str,
    ) -> AttendanceLogHomeSide:
        return resolve_home_side(
            support_team_id=support_team_id,
            home_team_id=home_team_id,
            away_team_id=away_team_id,
        )

    @staticmethod
    def _resolve_game_result(
        *,
        home_side: AttendanceLogHomeSide,
        home_score: int | None,
        away_score: int | None,
    ) -> AttendanceLogGameResult | None:
        return resolve_game_result(
            home_side=home_side,
            home_score=home_score,
            away_score=away_score,
        )

    def _find_cover_image_url(
        self,
        *,
        attendance_log_id: str,
    ) -> str | None:
        entries = self._log_entry_repository.get_all(
            attendance_log_id
        )

        for entry in entries:
            media_items = (
                self._get_log_media_repository()
                .get_all(
                    attendance_log_id,
                    entry.log_entry_id,
                )
            )

            for media in media_items:
                if (
                    media.media_type
                    != LogMediaType.IMAGE
                ):
                    continue

                if media.storage_path:
                    return (
                        self._get_storage_service()
                        .create_download_url(
                            media.storage_path
                        )
                    )

                if media.media_url:
                    return media.media_url

        return None

    def _to_entry_response(
        self,
        *,
        attendance_log_id: str,
        entry,
    ) -> LogEntryResponse:
        media_records = (
            self._get_log_media_repository()
            .get_all(
                attendance_log_id,
                entry.log_entry_id,
            )
        )

        media_responses = []

        for media in media_records:
            if media.storage_path:
                media_url = (
                    self._get_storage_service()
                    .create_download_url(
                        media.storage_path
                    )
                )
            elif media.media_url:
                media_url = media.media_url
            else:
                raise AppException(
                    status_code=status.HTTP_409_CONFLICT,
                    code="LOG_MEDIA_SOURCE_MISSING",
                    message=(
                        "직관 로그 미디어의 "
                        "파일 정보를 찾을 수 없습니다."
                    ),
                )

            media_responses.append(
                LogMediaResponse(
                    log_media_id=(
                        media.log_media_id
                    ),
                    media_type=media.media_type,
                    media_url=media_url,
                    thumbnail_url=(
                        media.thumbnail_url
                    ),
                    sequence_no=(
                        media.sequence_no
                    ),
                    created_at=media.created_at,
                )
            )

        return LogEntryResponse(
            log_entry_id=entry.log_entry_id,
            plan_item_id=entry.plan_item_id,
            place_id=entry.place_id,
            sequence_no=entry.sequence_no,
            entry_type=entry.entry_type,
            entry_title=entry.entry_title,
            review_text=entry.review_text,
            occurred_at=entry.occurred_at,
            media=media_responses,
            created_at=entry.created_at,
            updated_at=entry.updated_at,
        )

    @staticmethod
    def _to_log_response(
        record: AttendanceLogRecord,
    ) -> AttendanceLogResponse:
        return AttendanceLogResponse(
            attendance_log_id=(
                record.attendance_log_id
            ),
            trip_id=record.trip_id,
            game_id=record.game_id,
            plan_id=record.plan_id,
            log_title=record.log_title,
            summary_text=record.summary_text,
            seat=record.seat,
            log_status=record.log_status,
            visibility=record.visibility,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def _get_owned_trip_or_raise(
        self,
        *,
        user_id: str,
        trip_id: str,
    ) -> TripRecord:
        trip = self._trip_repository.get_by_id(
            trip_id
        )

        if trip is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="TRIP_NOT_FOUND",
                message="여행 정보를 찾을 수 없습니다.",
            )

        if trip.user_id != user_id:
            raise AppException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="TRIP_ACCESS_DENIED",
                message="해당 여행에 접근할 권한이 없습니다.",
            )

        return trip

    def _validate_duplicate_log(
        self,
        *,
        trip_id: str,
    ) -> None:
        existing = (
            self._attendance_log_repository
            .get_active_by_trip_id(
                trip_id
            )
        )

        if existing is not None:
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="ATTENDANCE_LOG_ALREADY_EXISTS",
                message=(
                    "해당 여행의 직관 로그가 "
                    "이미 존재합니다."
                ),
            )

    def _get_active_plan_or_raise(
        self,
        *,
        trip: TripRecord,
    ) -> ItineraryPlanRecord:
        if trip.active_plan_id is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="ITINERARY_PLAN_NOT_FOUND",
                message=(
                    "직관 로그를 생성할 일정 정보를 "
                    "찾을 수 없습니다."
                ),
            )

        plan = (
            self._itinerary_plan_repository
            .get_by_id(
                trip.active_plan_id
            )
        )

        if (
            plan is None
            or plan.status
            != ItineraryPlanStatus.ACTIVE
        ):
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="ITINERARY_PLAN_NOT_FOUND",
                message=(
                    "직관 로그를 생성할 활성 일정을 "
                    "찾을 수 없습니다."
                ),
            )

        return plan

    def _validate_game_exists(
        self,
        *,
        game_id: str,
    ) -> None:
        game = self._game_repository.get_by_id(
            game_id
        )

        if game is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="GAME_NOT_FOUND",
                message="경기 정보를 찾을 수 없습니다.",
            )

    def _create_entries(
        self,
        *,
        attendance_log_id: str,
        plan: ItineraryPlanRecord,
        now: datetime,
    ) -> None:
        sequence_no = 1

        for day in sorted(
            plan.days,
            key=lambda value: value.date,
        ):
            for item in sorted(
                day.items,
                key=lambda value: value.sequence,
            ):
                entry_type = (
                    self._to_log_entry_type(
                        item.item_type
                    )
                )

                if entry_type is None:
                    continue

                place_id = (
                    item.place_id
                    if item.item_type
                    == ItineraryItemType.PLACE
                    else None
                )

                entry = LogEntryDocument(
                    plan_item_id=item.item_id,
                    place_id=place_id,
                    sequence_no=sequence_no,
                    entry_type=entry_type,
                    entry_title=item.name,
                    review_text=None,
                    occurred_at=(
                        item.scheduled_start_at
                    ),
                    created_at=now,
                    updated_at=now,
                )

                self._log_entry_repository.create(
                    attendance_log_id,
                    entry,
                )

                sequence_no += 1

    @staticmethod
    def _to_log_entry_type(
        item_type: ItineraryItemType,
    ) -> LogEntryType | None:
        if item_type == ItineraryItemType.PLACE:
            return LogEntryType.PLACE

        if item_type == ItineraryItemType.STADIUM:
            return LogEntryType.GAME

        return None

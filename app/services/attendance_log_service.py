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
from app.repositories.trip_repository import TripRepository
from app.schemas.attendance_log import (
    AttendanceLogDocument,
    AttendanceLogRecord,
    AttendanceLogStatus,
    LogEntryDocument,
    LogEntryType,
)
from app.schemas.itinerary_plan import (
    ItineraryPlanRecord,
    ItineraryPlanStatus,
)
from app.schemas.trip import TripRecord


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

    def create_draft(
        self,
        *,
        user_id: str,
        trip_id: str,
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

        now = datetime.now(timezone.utc)

        log_document = AttendanceLogDocument(
            user_id=user_id,
            trip_id=trip.trip_id,
            game_id=trip.game_id,
            plan_id=plan.plan_id,
            log_title=trip.title,
            summary_text=None,
            log_status=AttendanceLogStatus.DRAFT,
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

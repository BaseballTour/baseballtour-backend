from datetime import datetime, timezone

from fastapi import status

from app.core.exceptions import AppException
from app.repositories.itinerary_plan_repository import (
    ItineraryPlanRepository,
)
from app.repositories.trip_repository import TripRepository
from app.schemas.itinerary_plan import ItineraryPlanRecord
from app.schemas.trip import TripRecord, TripStatus


class ItineraryPlanService:
    """생성된 여행 일정 Plan의 조회와 삭제를 담당합니다."""

    def __init__(
        self,
        trip_repository: TripRepository | None = None,
        itinerary_plan_repository: ItineraryPlanRepository | None = None,
    ) -> None:
        self._trip_repository = (
            trip_repository
            or TripRepository()
        )
        self._itinerary_plan_repository = (
            itinerary_plan_repository
            or ItineraryPlanRepository()
        )

    def get_active_plan(
        self,
        *,
        user_id: str,
        trip_id: str,
    ) -> ItineraryPlanRecord:
        """로그인 사용자의 현재 ACTIVE Plan을 조회합니다."""

        trip = self._get_owned_trip_or_raise(
            user_id=user_id,
            trip_id=trip_id,
        )

        return self._get_active_plan_or_raise(
            trip=trip,
            user_id=user_id,
        )

    def delete_active_plan(
        self,
        *,
        user_id: str,
        trip_id: str,
    ) -> None:
        """현재 ACTIVE Plan을 삭제합니다."""

        trip = self._get_owned_trip_or_raise(
            user_id=user_id,
            trip_id=trip_id,
        )

        if trip.status == TripStatus.GENERATING:
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="TRIP_GENERATION_IN_PROGRESS",
                message=(
                    "일정 생성이 진행 중인 동안에는 "
                    "현재 일정을 삭제할 수 없습니다."
                ),
            )

        plan = self._get_active_plan_or_raise(
            trip=trip,
            user_id=user_id,
        )

        self._itinerary_plan_repository.delete_active_plan(
            trip_id=trip_id,
            plan_id=plan.plan_id,
            updated_at=datetime.now(timezone.utc),
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

    def _get_active_plan_or_raise(
        self,
        *,
        trip: TripRecord,
        user_id: str,
    ) -> ItineraryPlanRecord:
        if trip.active_plan_id is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="ITINERARY_PLAN_NOT_FOUND",
                message="현재 활성화된 여행 일정이 없습니다.",
            )

        plan = self._itinerary_plan_repository.get_by_id(
            trip.active_plan_id
        )

        if (
            plan is None
            or plan.trip_id != trip.trip_id
            or plan.user_id != user_id
        ):
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="ITINERARY_PLAN_NOT_FOUND",
                message="현재 활성화된 여행 일정을 찾을 수 없습니다.",
            )

        return plan

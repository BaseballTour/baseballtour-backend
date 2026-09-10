from datetime import datetime
from fastapi import status

from app.core.exceptions import AppException
from app.repositories.itinerary_plan_repository import ItineraryPlanRepository
from app.repositories.trip_share_repository import TripShareRepository
from app.schemas.itinerary_plan import ItineraryPlanStatus
from app.schemas.trip import TripStatus
from app.services.trip_service import TripService


class TripShareService:
    """여행 공유 발급·해제·공개 조회를 담당합니다."""

    def __init__(
        self,
        share_repository: TripShareRepository | None = None,
        trip_service: TripService | None = None,
        plan_repository: ItineraryPlanRepository | None = None,
        game_service=None,
    ) -> None:
        self._share_repository = (
            share_repository
            if share_repository is not None
            else TripShareRepository()
        )
        self._trip_service = (
            trip_service
            if trip_service is not None
            else TripService()
        )
        self._plan_repository = (
            plan_repository
            if plan_repository is not None
            else ItineraryPlanRepository()
        )
        self._game_service = game_service

    def _get_game_service(self):
        if self._game_service is None:
            from app.services.game_service import GameService

            self._game_service = GameService()
        return self._game_service

    def issue(self, *, user_id: str, trip_id: str) -> str:
        """활성 일정이 있는 본인 여행의 공유 토큰을 발급합니다."""
        trip = self._trip_service.get_trip(
            user_id=user_id,
            trip_id=trip_id,
        )

        if (
            trip.status
            not in {
                TripStatus.GENERATED,
                TripStatus.COMPLETED,
                TripStatus.GENERATING,
            }
            or trip.active_plan_id is None
        ):
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="TRIP_SHARE_NOT_AVAILABLE",
                message="공유할 수 있는 활성 여행 일정이 없습니다.",
            )

        plan = self._plan_repository.get_by_id(trip.active_plan_id)
        if (
            plan is None
            or plan.trip_id != trip.trip_id
            or plan.user_id != user_id
            or plan.status != ItineraryPlanStatus.ACTIVE
        ):
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="TRIP_SHARE_NOT_AVAILABLE",
                message="공유할 수 있는 활성 여행 일정이 없습니다.",
            )

        token = self._share_repository.issue(
            trip_id=trip_id,
            user_id=user_id,
            expected_plan_id=plan.plan_id,
        )
        if token is None:
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="TRIP_SHARE_STATE_CHANGED",
                message="여행 또는 일정 상태가 변경되었습니다. 다시 시도해 주세요.",
            )

        return token

    def issue_with_metadata(
        self,
        *,
        user_id: str,
        trip_id: str,
    ) -> tuple[str, datetime, datetime | None]:
        """공유 토큰과 해당 토큰의 생성·해제 시각을 반환합니다."""
        token = self.issue(
            user_id=user_id,
            trip_id=trip_id,
        )

        metadata = self._share_repository.get_metadata(
            trip_id=trip_id,
            user_id=user_id,
            token=token,
        )
        if metadata is None:
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="TRIP_SHARE_STATE_CHANGED",
                message="공유 상태가 변경되었습니다. 다시 시도해 주세요.",
            )

        created_at, revoked_at = metadata
        return token, created_at, revoked_at

    def revoke(self, *, user_id: str, trip_id: str) -> bool:
        """본인 여행의 공유를 해제합니다."""
        self._trip_service.get_trip(
            user_id=user_id,
            trip_id=trip_id,
        )
        return self._share_repository.revoke(
            trip_id=trip_id,
            user_id=user_id,
        )

    def get_public_trip(self, *, token: str):
        """활성 공유 토큰에 연결된 공개 여행 정보를 반환합니다."""
        from app.services.trip_share_public import (
            resolve_shared_subtitle,
            to_shared_trip,
        )

        bundle = self._share_repository.get_active_bundle(token)
        if bundle is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="SHARE_NOT_FOUND",
                message="공유된 여행을 찾을 수 없습니다.",
            )

        trip, plan = bundle
        game = self._get_game_service().get_game(trip.game_id)

        return to_shared_trip(
            trip=trip,
            plan=plan,
            game=game,
            subtitle=resolve_shared_subtitle(trip),
        )

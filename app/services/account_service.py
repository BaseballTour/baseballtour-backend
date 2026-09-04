from datetime import datetime, timezone

from fastapi import status

from app.core.exceptions import AppException
from app.repositories.attendance_log_repository import (
    AttendanceLogRepository,
)
from app.repositories.favorite_collection_repository import (
    FavoriteCollectionRepository,
)
from app.repositories.itinerary_plan_repository import (
    ItineraryPlanRepository,
)
from app.repositories.place_selection_repository import (
    PlaceSelectionRepository,
)
from app.repositories.trip_repository import TripRepository
from app.repositories.user_repository import UserRepository
from app.services.storage_service import StorageService


class AccountService:
    """회원탈퇴와 사용자 소유 데이터 정리를 담당합니다."""

    def __init__(
        self,
        user_repository: UserRepository | None = None,
        trip_repository: TripRepository | None = None,
        place_selection_repository: (
            PlaceSelectionRepository | None
        ) = None,
        itinerary_plan_repository: (
            ItineraryPlanRepository | None
        ) = None,
        favorite_collection_repository: (
            FavoriteCollectionRepository | None
        ) = None,
        attendance_log_repository: (
            AttendanceLogRepository | None
        ) = None,
        storage_service: (
            StorageService | None
        ) = None,
    ) -> None:
        self._user_repository = (
            user_repository
            or UserRepository()
        )
        self._trip_repository = (
            trip_repository
            or TripRepository()
        )
        self._place_selection_repository = (
            place_selection_repository
            or PlaceSelectionRepository()
        )
        self._itinerary_plan_repository = (
            itinerary_plan_repository
            or ItineraryPlanRepository()
        )
        self._favorite_collection_repository = (
            favorite_collection_repository
            or FavoriteCollectionRepository()
        )
        self._attendance_log_repository = (
            attendance_log_repository
            or AttendanceLogRepository()
        )

        # 회원탈퇴 시에만 필요하므로 lazy 생성합니다.
        self._storage_service = storage_service

    def _get_storage_service(
        self,
    ) -> StorageService:
        if self._storage_service is None:
            self._storage_service = StorageService()

        return self._storage_service

    def withdraw_user(
        self,
        *,
        user_id: str,
    ) -> None:
        """사용자 소유 데이터를 정리하고 계정을 탈퇴 처리합니다."""

        deleted_at = datetime.now(
            timezone.utc
        )

        # Storage 장애 시 Firestore 데이터를 건드리기 전에
        # 회원탈퇴를 중단합니다.
        self._get_storage_service().delete_user_files(
            user_id
        )

        trips = self._trip_repository.get_by_user_id(
            user_id
        )

        for trip in trips:
            self._place_selection_repository.delete_all(
                trip_id=trip.trip_id,
            )

            self._itinerary_plan_repository.delete_all_by_trip_id(
                trip_id=trip.trip_id,
            )

            self._trip_repository.delete(
                trip.trip_id
            )

        self._favorite_collection_repository.delete_all_by_user_id(
            user_id=user_id,
        )

        self._attendance_log_repository.soft_delete_all_by_user_id(
            user_id,
            deleted_at=deleted_at,
        )

        deleted = self._user_repository.soft_delete(
            user_id,
            deleted_at=deleted_at,
        )

        if not deleted:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="USER_NOT_FOUND",
                message="사용자 정보를 찾을 수 없습니다.",
            )

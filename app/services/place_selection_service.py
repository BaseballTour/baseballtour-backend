from datetime import datetime, timezone

from fastapi import status

from app.core.exceptions import AppException
from app.repositories.place_selection_repository import (
    PlaceSelectionRepository,
)
from app.repositories.trip_repository import TripRepository
from app.schemas.place_selection import (
    PlaceSelectionCreateRequest,
    PlaceSelectionDocument,
    PlaceSelectionRecord,
)
from app.schemas.trip import TripRecord


class PlaceSelectionService:
    """여행별 장소 선택 비즈니스 로직을 담당합니다."""

    def __init__(
        self,
        place_selection_repository: PlaceSelectionRepository | None = None,
        trip_repository: TripRepository | None = None,
    ) -> None:
        self._place_selection_repository = (
            place_selection_repository
            or PlaceSelectionRepository()
        )
        self._trip_repository = (
            trip_repository
            or TripRepository()
        )

    def create_selection(
        self,
        *,
        user_id: str,
        trip_id: str,
        request: PlaceSelectionCreateRequest,
    ) -> PlaceSelectionRecord:
        """로그인 사용자의 여행에 장소를 선택합니다."""

        self._get_owned_trip_or_raise(
            user_id=user_id,
            trip_id=trip_id,
        )

        selection = PlaceSelectionDocument(
            place_id=request.place_id,
            is_required=request.is_required,
            created_at=datetime.now(timezone.utc),
        )

        created = self._place_selection_repository.create(
            trip_id=trip_id,
            selection=selection,
        )

        if created is None:
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="PLACE_SELECTION_ALREADY_EXISTS",
                message="이미 선택된 장소입니다.",
            )

        return created

    def get_selections(
        self,
        *,
        user_id: str,
        trip_id: str,
    ) -> list[PlaceSelectionRecord]:
        """로그인 사용자의 여행에 선택된 장소 목록을 조회합니다."""

        self._get_owned_trip_or_raise(
            user_id=user_id,
            trip_id=trip_id,
        )

        return self._place_selection_repository.get_all(
            trip_id=trip_id,
        )

    def delete_selection(
        self,
        *,
        user_id: str,
        trip_id: str,
        place_id: str,
    ) -> None:
        """로그인 사용자의 여행에서 선택된 장소를 삭제합니다."""

        self._get_owned_trip_or_raise(
            user_id=user_id,
            trip_id=trip_id,
        )

        deleted = self._place_selection_repository.delete(
            trip_id=trip_id,
            place_id=place_id,
        )

        if not deleted:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="PLACE_SELECTION_NOT_FOUND",
                message="선택된 장소를 찾을 수 없습니다.",
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

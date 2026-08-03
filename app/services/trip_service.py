from datetime import datetime, timezone

from fastapi import status
from pydantic import ValidationError

from app.core.exceptions import AppException
from app.repositories.game_repository import GameRepository
from app.repositories.trip_repository import TripRepository
from app.schemas.game import GameRecord
from app.schemas.trip import (
    TripCreateRequest,
    TripDocument,
    TripRecord,
    TripStatus,
    TripUpdateRequest,
)


class TripService:
    """여행 생성, 조회, 수정, 삭제 로직을 담당합니다."""

    def __init__(
        self,
        trip_repository: TripRepository | None = None,
        game_repository: GameRepository | None = None,
    ) -> None:
        self._trip_repository = (
            trip_repository
            or TripRepository()
        )
        self._game_repository = (
            game_repository
            or GameRepository()
        )

    def create_trip(
        self,
        *,
        user_id: str,
        request: TripCreateRequest,
    ) -> TripRecord:
        """로그인 사용자의 여행을 생성합니다."""

        game = self._get_game_or_raise(
            request.game_id
        )

        self._validate_game_in_trip_period(
            game=game,
            trip_start_at=request.trip_start_at,
            trip_end_at=request.trip_end_at,
        )

        now = datetime.now(timezone.utc)

        trip = TripDocument(
            user_id=user_id,
            game_id=request.game_id,
            title=request.title,
            trip_start_at=request.trip_start_at,
            trip_end_at=request.trip_end_at,
            arrival_point=request.arrival_point,
            departure_point=request.departure_point,
            accommodation=request.accommodation,
            status=TripStatus.PLANNING,
            active_plan_id=None,
            created_at=now,
            updated_at=now,
        )

        return self._trip_repository.create(trip)

    def get_my_trips(
        self,
        *,
        user_id: str,
    ) -> list[TripRecord]:
        """로그인 사용자가 소유한 여행 목록을 반환합니다."""

        return self._trip_repository.get_by_user_id(
            user_id
        )

    def get_trip(
        self,
        *,
        user_id: str,
        trip_id: str,
    ) -> TripRecord:
        """로그인 사용자가 소유한 여행을 조회합니다."""

        return self._get_owned_trip_or_raise(
            user_id=user_id,
            trip_id=trip_id,
        )

    def update_trip(
        self,
        *,
        user_id: str,
        trip_id: str,
        request: TripUpdateRequest,
    ) -> TripRecord:
        """로그인 사용자가 소유한 여행 기본정보를 수정합니다."""

        current_trip = self._get_owned_trip_or_raise(
            user_id=user_id,
            trip_id=trip_id,
        )

        request_data = request.model_dump(
            by_alias=False,
            exclude_unset=True,
        )

        if not request_data:
            return current_trip

        merged_data = current_trip.model_dump(
            by_alias=False,
            exclude={"trip_id"},
        )
        merged_data.update(request_data)

        now = datetime.now(timezone.utc)
        merged_data["updated_at"] = now

        try:
            validated_trip = TripDocument.model_validate(
                merged_data
            )
        except ValidationError as error:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="TRIP_TIME_INVALID",
                message=(
                    "여행 종료시간은 시작시간보다 "
                    "늦어야 합니다."
                ),
            ) from error

        game = self._get_game_or_raise(
            validated_trip.game_id
        )

        self._validate_game_in_trip_period(
            game=game,
            trip_start_at=validated_trip.trip_start_at,
            trip_end_at=validated_trip.trip_end_at,
        )

        updates = request.model_dump(
            by_alias=True,
            exclude_unset=True,
        )
        updates["updatedAt"] = now

        updated_trip = self._trip_repository.update(
            trip_id,
            updates,
        )

        if updated_trip is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="TRIP_NOT_FOUND",
                message="여행 정보를 찾을 수 없습니다.",
            )

        return updated_trip

    def delete_trip(
        self,
        *,
        user_id: str,
        trip_id: str,
    ) -> None:
        """로그인 사용자가 소유한 여행을 삭제합니다."""

        self._get_owned_trip_or_raise(
            user_id=user_id,
            trip_id=trip_id,
        )

        deleted = self._trip_repository.delete(
            trip_id
        )

        if not deleted:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="TRIP_NOT_FOUND",
                message="여행 정보를 찾을 수 없습니다.",
            )

    def _get_game_or_raise(
        self,
        game_id: str,
    ) -> GameRecord:
        game = self._game_repository.get_by_id(
            game_id
        )

        if game is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="GAME_NOT_FOUND",
                message="경기 정보를 찾을 수 없습니다.",
            )

        return game

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

    @staticmethod
    def _validate_game_in_trip_period(
        *,
        game: GameRecord,
        trip_start_at: datetime,
        trip_end_at: datetime,
    ) -> None:
        if not (
            trip_start_at
            <= game.game_start_at
            <= trip_end_at
        ):
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="GAME_OUTSIDE_TRIP_PERIOD",
                message=(
                    "경기시간이 여행 기간에 "
                    "포함되지 않습니다."
                ),
            )

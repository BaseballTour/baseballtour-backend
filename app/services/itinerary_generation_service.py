import asyncio
from collections.abc import Callable
from datetime import datetime, timezone

from fastapi import status
from pydantic import ValidationError

from app.algorithms.itinerary_generator import generate_itinerary
from app.algorithms.travel_time import (
    TravelTimeMatrix,
    TravelTimeProvider,
    build_itinerary_travel_time_matrix,
)
from app.core.exceptions import AppException
from app.external.odsay.client import get_cached_transit_minutes
from app.external.tour_api.adapter import (
    TourApiAdapter,
    tour_api_adapter,
)
from app.models.itinerary import (
    GameAnchor,
    GeoPoint,
    ItineraryResult,
    SelectedPlaceInput,
    TripInput,
)
from app.models.place import Place
from app.repositories.game_repository import GameRepository
from app.repositories.itinerary_plan_repository import (
    ItineraryPlanRepository,
)
from app.repositories.place_selection_repository import (
    PlaceSelectionRepository,
)
from app.repositories.stadium_repository import StadiumRepository
from app.repositories.trip_repository import TripRepository
from app.schemas.game import GameRecord
from app.schemas.itinerary_plan import (
    ItineraryPlanDocument,
    ItineraryPlanRecord,
)
from app.schemas.stadium import StadiumResponse
from app.schemas.trip import TripRecord, TripStatus
from app.services.recommendation import (
    RecommendationCenter,
    RecommendationService,
)


ItineraryGenerator = Callable[..., ItineraryResult]
RECOMMENDATION_TIMEOUT_SECONDS = 20.0


class ItineraryGenerationService:
    """여행 데이터를 조합해 일정 Plan을 생성합니다."""

    def __init__(
        self,
        trip_repository: TripRepository | None = None,
        game_repository: GameRepository | None = None,
        stadium_repository: StadiumRepository | None = None,
        place_selection_repository: PlaceSelectionRepository | None = None,
        itinerary_plan_repository: ItineraryPlanRepository | None = None,
        place_adapter: TourApiAdapter | None = None,
        recommendation_service: RecommendationService | None = None,
        travel_time_provider: TravelTimeProvider = get_cached_transit_minutes,
        generator: ItineraryGenerator = generate_itinerary,
    ) -> None:
        self._trip_repository = (
            trip_repository
            or TripRepository()
        )
        self._game_repository = (
            game_repository
            or GameRepository()
        )
        self._stadium_repository = (
            stadium_repository
            or StadiumRepository()
        )
        self._place_selection_repository = (
            place_selection_repository
            or PlaceSelectionRepository()
        )
        self._itinerary_plan_repository = (
            itinerary_plan_repository
            or ItineraryPlanRepository()
        )
        self._place_adapter = (
            place_adapter
            or tour_api_adapter
        )
        self._recommendation_service = (
            recommendation_service
            or RecommendationService(self._place_adapter)
        )
        self._travel_time_provider = travel_time_provider
        self._generator = generator

    async def generate(
        self,
        *,
        user_id: str,
        trip_id: str,
    ) -> ItineraryPlanRecord:
        """로그인 사용자의 여행 일정을 생성하고 저장합니다."""

        trip = self._get_owned_trip_or_raise(
            user_id=user_id,
            trip_id=trip_id,
        )

        self._validate_generation_status(trip)
        self._validate_required_points(trip)

        original_status = trip.status
        generation_started = False

        try:
            self._update_trip_status(
                trip_id=trip_id,
                trip_status=TripStatus.GENERATING,
            )
            generation_started = True

            game = self._get_game_or_raise(
                trip.game_id
            )
            stadium = self._get_stadium_or_raise(
                game.stadium_id
            )

            selections = (
                self._place_selection_repository.get_all(
                    trip_id=trip_id,
                )
            )

            trip_input = self._build_trip_input(
                trip=trip,
                game=game,
                stadium=stadium,
                selections=selections,
            )

            places = await self._resolve_places(
                selections
            )

            try:
                recommended_places = await asyncio.wait_for(
                    self._recommendation_service.get_candidates(
                        centers=[
                            RecommendationCenter(
                                latitude=stadium.latitude,
                                longitude=stadium.longitude,
                            ),
                            RecommendationCenter(
                                latitude=trip.arrival_point.latitude,
                                longitude=trip.arrival_point.longitude,
                            ),
                        ],
                        selected_place_ids=(
                            selection.place_id
                            for selection in selections
                        ),
                    ),
                    timeout=RECOMMENDATION_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                recommended_places = []

            matrix_places = list(
                {
                    place.place_id: place
                    for place in [*places, *recommended_places]
                }.values()
            )

            matrix = (
                await build_itinerary_travel_time_matrix(
                    trip_input,
                    matrix_places,
                    provider=self._travel_time_provider,
                )
            )

            result = self._generator(
                trip_input,
                places,
                matrix,
                recommended_places=recommended_places,
            )

            now = datetime.now(timezone.utc)

            plan = self._build_plan_document(
                user_id=user_id,
                result=result,
                now=now,
            )

            return (
                self._itinerary_plan_repository
                .commit_generated_plan(
                    trip_id=trip_id,
                    plan=plan,
                    previous_plan_id=trip.active_plan_id,
                )
            )

        except asyncio.CancelledError:
            if generation_started:
                self._restore_trip_status(
                    trip_id=trip_id,
                    original_status=original_status,
                )
            raise
        except Exception:
            if generation_started:
                self._restore_trip_status(
                    trip_id=trip_id,
                    original_status=original_status,
                )
            raise

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
    def _validate_generation_status(
        trip: TripRecord,
    ) -> None:
        if trip.status == TripStatus.GENERATING:
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="TRIP_GENERATION_IN_PROGRESS",
                message="이미 일정 생성이 진행 중입니다.",
            )

        if trip.status in {
            TripStatus.COMPLETED,
            TripStatus.CANCELLED,
        }:
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="TRIP_STATUS_INVALID",
                message=(
                    "현재 여행 상태에서는 "
                    "일정을 생성할 수 없습니다."
                ),
            )

    @staticmethod
    def _validate_required_points(
        trip: TripRecord,
    ) -> None:
        missing: list[str] = []

        if trip.arrival_point is None:
            missing.append("arrivalPoint")

        if trip.departure_point is None:
            missing.append("departurePoint")

        if missing:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="TRIP_POINTS_REQUIRED",
                message=(
                    "일정 생성을 위해 도착지와 "
                    "출발지 정보가 필요합니다."
                ),
                details={
                    "missingFields": missing,
                },
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

    def _get_stadium_or_raise(
        self,
        stadium_id: str,
    ) -> StadiumResponse:
        stadium = self._stadium_repository.get_by_id(
            stadium_id
        )

        if stadium is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="STADIUM_NOT_FOUND",
                message="구장 정보를 찾을 수 없습니다.",
            )

        return stadium

    @staticmethod
    def _build_trip_input(
        *,
        trip: TripRecord,
        game: GameRecord,
        stadium: StadiumResponse,
        selections,
    ) -> TripInput:
        assert trip.arrival_point is not None
        assert trip.departure_point is not None

        accommodation = None

        if trip.accommodation is not None:
            accommodation = GeoPoint(
                name=trip.accommodation.name,
                address=trip.accommodation.address,
                latitude=trip.accommodation.latitude,
                longitude=trip.accommodation.longitude,
            )

        try:
            return TripInput(
                trip_id=trip.trip_id,
                trip_start_at=trip.trip_start_at,
                trip_end_at=trip.trip_end_at,
                arrival_point=GeoPoint(
                    name=trip.arrival_point.name,
                    latitude=trip.arrival_point.latitude,
                    longitude=trip.arrival_point.longitude,
                ),
                departure_point=GeoPoint(
                    name=trip.departure_point.name,
                    latitude=trip.departure_point.latitude,
                    longitude=trip.departure_point.longitude,
                ),
                accommodation=accommodation,
                game_anchor=GameAnchor(
                    game_id=game.game_id,
                    stadium_id=stadium.stadium_id,
                    name=stadium.name,
                    address=stadium.address,
                    latitude=stadium.latitude,
                    longitude=stadium.longitude,
                    game_start_at=game.game_start_at,
                    required_arrival_minutes=40,
                ),
                selected_places=[
                    SelectedPlaceInput(
                        place_id=selection.place_id,
                        is_required=selection.is_required,
                    )
                    for selection in selections
                ],
            )
        except ValidationError as error:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="ITINERARY_INPUT_INVALID",
                message=(
                    "일정 생성에 필요한 여행 데이터가 "
                    "올바르지 않습니다."
                ),
                details={
                    "errors": error.errors(
                        include_url=False
                    ),
                },
            ) from error

    async def _resolve_places(
        self,
        selections,
    ) -> list[Place]:
        places: list[Place] = []

        for selection in selections:
            place_id = selection.place_id

            prefix = "tour_"

            if not place_id.startswith(prefix):
                continue

            content_id = place_id[len(prefix):]

            if not content_id:
                continue

            try:
                place = await self._place_adapter.get_place_detail(
                    content_id
                )
            except ValueError:
                # 실제 장소 상세가 존재하지 않으면 알고리즘에서
                # INVALID_PLACE 제외 사유를 만들 수 있도록 생략합니다.
                continue

            places.append(place)

        return places

    def _update_trip_status(
        self,
        *,
        trip_id: str,
        trip_status: TripStatus,
    ) -> None:
        updated = self._trip_repository.update(
            trip_id,
            {
                "status": trip_status.value,
                "updatedAt": datetime.now(timezone.utc),
            },
        )

        if updated is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="TRIP_NOT_FOUND",
                message="여행 정보를 찾을 수 없습니다.",
            )

    def _restore_trip_status(
        self,
        *,
        trip_id: str,
        original_status: TripStatus,
    ) -> None:
        try:
            self._trip_repository.update(
                trip_id,
                {
                    "status": original_status.value,
                    "updatedAt": datetime.now(timezone.utc),
                },
            )
        except Exception:
            # 원래 예외를 덮어쓰지 않습니다.
            pass

    @staticmethod
    def _build_plan_document(
        *,
        user_id: str,
        result: ItineraryResult,
        now: datetime,
    ) -> ItineraryPlanDocument:
        stored_days = [
            {
                **day.model_dump(
                    by_alias=True
                ),
                "items": [
                    {
                        **item.model_dump(
                            by_alias=True
                        ),
                        "itemId": (
                            f"item_{day_index}_{item_index}"
                        ),
                    }
                    for item_index, item in enumerate(
                        day.items,
                        start=1,
                    )
                ],
            }
            for day_index, day in enumerate(
                result.days,
                start=1,
            )
        ]

        return ItineraryPlanDocument(
            trip_id=result.trip_id,
            user_id=user_id,
            algorithm_version=result.algorithm_version,
            total_travel_minutes=(
                result.total_travel_minutes
            ),
            days=stored_days,
            excluded_places=result.excluded_places,
            created_at=now,
            updated_at=now,
        )

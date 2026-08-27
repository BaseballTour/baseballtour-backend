import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import status
from pydantic import ValidationError

from app.algorithms.itinerary_generator import generate_itinerary
from app.algorithms.travel_time import (
    TravelTimeMatrix,
    TravelTimeProvider,
    build_itinerary_travel_time_matrix,
)
from app.core.exceptions import AppException
from app.external.kakao.routing import get_cached_fastest_route
from app.external.tour_api.adapter import (
    TourApiAdapter,
    tour_api_adapter,
)
from app.models.itinerary import (
    GameAnchor,
    GeoPoint,
    ItineraryItemAddedBy,
    ItineraryItemType,
    ItineraryResult,
    RecommendationSummary,
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
    ItineraryPlanDay,
    ItineraryPlanDocument,
    ItineraryPlanItem,
    ItineraryPlanRecord,
)
from app.schemas.stadium import StadiumResponse
from app.schemas.trip import TripRecord, TripStatus
from app.services.recommendation import (
    ExcludedRecommendationPlace,
    RecommendationCenter,
    RecommendationService,
)


ItineraryGenerator = Callable[..., ItineraryResult]
RECOMMENDATION_TIMEOUT_SECONDS = 20.0
KOREA_TIMEZONE = ZoneInfo("Asia/Seoul")


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
        travel_time_provider: TravelTimeProvider = get_cached_fastest_route,
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
            trip = self._claim_generation_or_raise(
                trip=trip,
            )
            generation_started = True

            game = self._get_game_or_raise(
                trip.game_id
            )
            self._validate_game_in_trip_period(
                trip=trip,
                game=game,
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

            previous_plan = self._get_previous_plan(trip.active_plan_id)
            fixed_items = self._fixed_place_items(previous_plan)
            fixed_place_ids = {
                item.place_id for _, item in fixed_items if item.place_id
            }
            fixed_places = await self._resolve_place_ids(fixed_place_ids)

            rejected_recommendation_ids = set(
                trip.rejected_recommendation_place_ids
            )
            rejected_recommendation_ids.update(
                self._get_previous_unfixed_recommendation_ids(
                    trip.active_plan_id
                )
            )
            recommendation_excluded_ids = {
                selection.place_id for selection in selections
            } | rejected_recommendation_ids | fixed_place_ids

            try:
                recommendation_diagnostics: dict[str, object] = {}
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
                        selected_place_ids=recommendation_excluded_ids,
                        excluded_places=[
                            ExcludedRecommendationPlace(
                                name=stadium.name,
                                latitude=stadium.latitude,
                                longitude=stadium.longitude,
                            )
                        ],
                        travel_start_date=trip_input.trip_start_at.date(),
                        travel_end_date=trip_input.trip_end_at.date(),
                        diagnostics=recommendation_diagnostics,
                    ),
                    timeout=RECOMMENDATION_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                recommended_places = []
                recommendation_diagnostics = {
                    "filteredCounts": {"RECOMMENDATION_TIMEOUT": 1}
                }

            matrix_places = list(
                {
                    place.place_id: place
                    for place in [*places, *fixed_places, *recommended_places]
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
                recommendation_diagnostics=recommendation_diagnostics,
            )
            result = result.model_copy(
                update={
                    "recommendation_summary": RecommendationSummary(
                        fetched_count=int(
                            recommendation_diagnostics.get("fetchedCount", 0)
                        ),
                        candidate_count=int(
                            recommendation_diagnostics.get(
                                "candidateCount", len(recommended_places)
                            )
                        ),
                        scheduled_count=int(
                            recommendation_diagnostics.get(
                                "scheduledCount",
                                result.auto_recommended_place_count,
                            )
                        ),
                        category_distribution=dict(
                            recommendation_diagnostics.get(
                                "categoryDistribution", {}
                            )
                        ),
                        filtered_counts=dict(
                            recommendation_diagnostics.get("filteredCounts", {})
                        ),
                        placement_rejected_attempts=dict(
                            recommendation_diagnostics.get(
                                "placementRejectedAttempts", {}
                            )
                        ),
                    )
                }
            )

            now = datetime.now(timezone.utc)

            plan = self._build_plan_document(
                user_id=user_id,
                result=result,
                now=now,
            )
            plan = self._preserve_fixed_items(
                plan=plan,
                fixed_items=fixed_items,
            )

            return (
                self._itinerary_plan_repository
                .commit_generated_plan(
                    trip_id=trip_id,
                    plan=plan,
                    previous_plan_id=trip.active_plan_id,
                    rejected_recommendation_place_ids=sorted(
                        rejected_recommendation_ids
                    ),
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

    def _get_previous_unfixed_recommendation_ids(
        self,
        plan_id: str | None,
    ) -> set[str]:
        """재생성 시 사용자가 고정하지 않은 이전 자동 추천을 반복하지 않는다."""
        if plan_id is None:
            return set()

        plan = self._itinerary_plan_repository.get_by_id(plan_id)
        if plan is None:
            return set()

        return {
            item.place_id
            for day in plan.days
            for item in day.items
            if item.item_type == ItineraryItemType.PLACE
            and item.added_by == ItineraryItemAddedBy.ALGORITHM
            and not item.is_fixed
            and item.place_id is not None
        }

    def _get_previous_plan(self, plan_id: str | None):
        if plan_id is None:
            return None
        return self._itinerary_plan_repository.get_by_id(plan_id)

    @staticmethod
    def _fixed_place_items(previous_plan) -> list[tuple[object, ItineraryPlanItem]]:
        if previous_plan is None:
            return []
        return [
            (day.date, item)
            for day in previous_plan.days
            for item in day.items
            if item.item_type == ItineraryItemType.PLACE
            and item.is_fixed
            and getattr(day, "date", None) is not None
            and getattr(item, "item_id", None) is not None
        ]

    async def _resolve_place_ids(self, place_ids: set[str]) -> list[Place]:
        selections = [
            type("FixedSelection", (), {"place_id": place_id})()
            for place_id in place_ids
        ]
        return await self._resolve_places(selections)

    @staticmethod
    def _preserve_fixed_items(
        *,
        plan: ItineraryPlanDocument,
        fixed_items: list[tuple[object, ItineraryPlanItem]],
    ) -> ItineraryPlanDocument:
        """재생성 결과에 기존 고정 PLACE의 날짜·시간·itemId를 보존합니다."""

        if not fixed_items:
            return plan
        fixed_ids = {item.place_id for _, item in fixed_items if item.place_id}
        days = [
            day.model_copy(
                update={
                    "items": [
                        item
                        for item in day.items
                        if not (
                            item.item_type == ItineraryItemType.PLACE
                            and item.place_id in fixed_ids
                        )
                    ]
                }
            )
            for day in plan.days
        ]

        for target_date, fixed in fixed_items:
            day_index = next(
                (index for index, day in enumerate(days) if day.date == target_date),
                None,
            )
            if day_index is None:
                raise AppException(
                    status_code=status.HTTP_409_CONFLICT,
                    code="FIXED_ITEM_OUTSIDE_TRIP",
                    message="고정한 장소의 날짜가 현재 여행 기간에 없습니다.",
                    details={
                        "date": target_date.isoformat(),
                        "conflictingItem": (
                            ItineraryGenerationService._item_conflict_details(fixed)
                        ),
                    },
                )
            day = days[day_index]
            retained: list[ItineraryPlanItem] = []
            for item in day.items:
                overlaps = (
                    item.scheduled_start_at < fixed.scheduled_end_at
                    and fixed.scheduled_start_at < item.scheduled_end_at
                )
                if not overlaps:
                    retained.append(item)
                    continue
                if (
                    item.item_type == ItineraryItemType.PLACE
                    and item.added_by == ItineraryItemAddedBy.ALGORITHM
                    and not item.is_fixed
                ):
                    continue
                raise AppException(
                    status_code=status.HTTP_409_CONFLICT,
                    code="FIXED_ITEM_TIME_CONFLICT",
                    message="고정한 장소가 필수 일정 또는 사용자 장소와 충돌합니다.",
                    details={
                        "date": target_date.isoformat(),
                        "fixedItem": (
                            ItineraryGenerationService._item_conflict_details(fixed)
                        ),
                        "conflictingItem": (
                            ItineraryGenerationService._item_conflict_details(item)
                        ),
                    },
                )
            retained.append(fixed)
            retained.sort(key=lambda item: item.scheduled_start_at)
            retained = [
                item.model_copy(update={"sequence": index})
                for index, item in enumerate(retained, start=1)
            ]
            days[day_index] = day.model_copy(update={"items": retained})

        total = sum(
            item.travel_minutes_from_previous
            for day in days
            for item in day.items
        )
        return plan.model_copy(
            update={"days": days, "total_travel_minutes": total}
        )

    @staticmethod
    def _item_conflict_details(item: ItineraryPlanItem) -> dict[str, object]:
        """충돌한 일정 항목을 클라이언트가 식별할 수 있는 정보."""

        return {
            "itemId": item.item_id,
            "type": item.item_type.value,
            "placeId": item.place_id,
            "name": item.name,
            "scheduledStartAt": item.scheduled_start_at.isoformat(),
            "scheduledEndAt": item.scheduled_end_at.isoformat(),
        }

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

    @staticmethod
    def _validate_game_in_trip_period(
        *,
        trip: TripRecord,
        game: GameRecord,
    ) -> None:
        if not (
            trip.trip_start_at
            <= game.game_start_at
            <= trip.trip_end_at
        ):
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="GAME_OUTSIDE_TRIP_PERIOD",
                message=(
                    "경기시간이 여행 기간에 "
                    "포함되지 않습니다."
                ),
                details={
                    "gameId": game.game_id,
                    "gameStartAt": game.game_start_at.isoformat(),
                    "tripStartAt": trip.trip_start_at.isoformat(),
                    "tripEndAt": trip.trip_end_at.isoformat(),
                },
            )

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
                trip_start_at=trip.trip_start_at.astimezone(
                    KOREA_TIMEZONE
                ),
                trip_end_at=trip.trip_end_at.astimezone(
                    KOREA_TIMEZONE
                ),
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
                    game_start_at=game.game_start_at.astimezone(
                        KOREA_TIMEZONE
                    ),
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

    def _claim_generation_or_raise(
        self,
        *,
        trip: TripRecord,
    ) -> TripRecord:
        claimed = self._trip_repository.claim_generation(
            trip_id=trip.trip_id,
            expected_status=trip.status,
            updated_at=datetime.now(timezone.utc),
        )

        if claimed is not None:
            return claimed

        current = self._trip_repository.get_by_id(
            trip.trip_id
        )

        if current is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="TRIP_NOT_FOUND",
                message="여행 정보를 찾을 수 없습니다.",
            )

        self._validate_generation_status(current)

        raise AppException(
            status_code=status.HTTP_409_CONFLICT,
            code="TRIP_GENERATION_STATE_CHANGED",
            message=(
                "여행 상태가 변경되어 "
                "일정 생성을 시작할 수 없습니다."
            ),
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
            recommendation_summary=result.recommendation_summary,
            created_at=now,
            updated_at=now,
        )

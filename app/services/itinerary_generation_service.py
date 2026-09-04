import asyncio
from collections import Counter
from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone
import logging
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
    DayType,
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
RECOMMENDATION_TIMEOUT_SECONDS = 45.0
SUPPLEMENT_GAP_MINUTES = 150
GENERATION_STALE_AFTER = timedelta(minutes=10)
KOREA_TIMEZONE = ZoneInfo("Asia/Seoul")
logger = logging.getLogger(__name__)


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

    async def get_recommendation_candidates(
        self,
        *,
        user_id: str,
        trip_id: str,
    ) -> list[Place]:
        """일정 생성 전에 프론트가 선택할 주변 추천 후보를 반환합니다."""

        trip = self._get_owned_trip_or_raise(
            user_id=user_id,
            trip_id=trip_id,
        )
        self._validate_required_points(trip)
        game = self._get_game_or_raise(trip.game_id)
        stadium = self._get_stadium_or_raise(game.stadium_id)
        selections = self._place_selection_repository.get_all(
            trip_id=trip_id,
        )
        return await self._recommendation_service.get_candidates(
            centers=self._recommendation_centers(
                trip=trip,
                stadium=stadium,
            ),
            selected_place_ids={
                selection.place_id for selection in selections
            },
            excluded_places=[
                ExcludedRecommendationPlace(
                    name=stadium.name,
                    latitude=stadium.latitude,
                    longitude=stadium.longitude,
                )
            ],
            travel_start_date=trip.trip_start_at.date(),
            travel_end_date=trip.trip_end_at.date(),
        )

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
        trip = self._recover_stale_generation(trip)

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
                        centers=self._recommendation_centers(
                            trip=trip,
                            stadium=stadium,
                        ),
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
                logger.warning(
                    "추천 장소 조회 시간 초과, 선택 장소와 Anchor로 "
                    "축소 일정을 생성합니다: trip_id=%s",
                    trip_id,
                )
                recommended_places = []
                recommendation_diagnostics["filteredCounts"] = {
                    "RECOMMENDATION_TIMEOUT": 1,
                }
            except AppException as error:
                logger.warning(
                    "추천 외부 API 실패, 선택 장소와 Anchor로 축소 "
                    "일정을 생성합니다: trip_id=%s code=%s",
                    trip_id,
                    error.code,
                )
                recommended_places = []
                recommendation_diagnostics["filteredCounts"] = {
                    "RECOMMENDATION_EXTERNAL_API_FAILED": 1,
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
            supplement_dates = self._recommendation_supplement_dates(result)
            if supplement_dates:
                supplemental_diagnostics: dict[str, object] = {}
                try:
                    supplemental_places = await asyncio.wait_for(
                        self._recommendation_service.get_candidates(
                            centers=self._supplement_recommendation_centers(
                                result=result,
                                target_dates=supplement_dates,
                            ),
                            selected_place_ids=(
                                recommendation_excluded_ids
                                | {place.place_id for place in recommended_places}
                            ),
                            excluded_places=[
                                ExcludedRecommendationPlace(
                                    name=stadium.name,
                                    latitude=stadium.latitude,
                                    longitude=stadium.longitude,
                                )
                            ],
                            travel_start_date=min(supplement_dates),
                            travel_end_date=max(supplement_dates),
                            diagnostics=supplemental_diagnostics,
                        ),
                        timeout=RECOMMENDATION_TIMEOUT_SECONDS,
                    )
                except (asyncio.TimeoutError, AppException) as error:
                    logger.warning(
                        "부족 날짜 추천 보충을 건너뜁니다: trip_id=%s "
                        "dates=%s reason=%s",
                        trip_id,
                        [item.isoformat() for item in supplement_dates],
                        error,
                    )
                    supplemental_places = []

                if supplemental_places:
                    matrix_places.extend(supplemental_places)
                    matrix = await build_itinerary_travel_time_matrix(
                        trip_input,
                        list(
                            {
                                place.place_id: place
                                for place in matrix_places
                            }.values()
                        ),
                        provider=self._travel_time_provider,
                    )
                    result = self._generator(
                        trip_input,
                        places,
                        matrix,
                        recommended_places=recommended_places,
                        supplemental_recommendations_by_date={
                            target_date: supplemental_places
                            for target_date in supplement_dates
                        },
                        recommendation_diagnostics=recommendation_diagnostics,
                    )
                    self._merge_recommendation_fetch_diagnostics(
                        recommendation_diagnostics,
                        supplemental_diagnostics,
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

    @staticmethod
    def _recommendation_supplement_dates(
        result: ItineraryResult,
    ) -> list[date]:
        """1차 결과에서 자동 추천이 부족한 자유 일정 날짜만 고른다."""

        minimums = {
            DayType.ARRIVAL_DAY: 3,
            DayType.GAME_DAY: 2,
            DayType.NON_GAME_DAY: 4,
            DayType.DEPARTURE_DAY: 3,
        }
        targets: list[date] = []
        for day in result.days:
            minimum = minimums.get(day.day_type)
            if minimum is None:
                continue
            automatic_count = sum(
                item.added_by == ItineraryItemAddedBy.ALGORITHM
                for item in day.items
            )
            if automatic_count < minimum or (
                ItineraryGenerationService._has_supplementable_gap(day)
            ):
                targets.append(day.date)
        return targets

    @staticmethod
    def _has_supplementable_gap(day) -> bool:
        items = sorted(day.items, key=lambda item: item.scheduled_start_at)
        if not items:
            return True
        timezone_info = items[0].scheduled_start_at.tzinfo
        cursor = datetime.combine(day.date, time(9, 0), timezone_info)
        arrival = next(
            (
                item
                for item in items
                if item.item_type == ItineraryItemType.ARRIVAL_POINT
            ),
            None,
        )
        if arrival is not None:
            cursor = max(cursor, arrival.scheduled_end_at)
        closing_anchor = next(
            (
                item
                for item in items
                if item.item_type
                in {
                    ItineraryItemType.STADIUM,
                    ItineraryItemType.DEPARTURE_POINT,
                }
            ),
            None,
        )
        available_end = (
            closing_anchor.scheduled_start_at
            if closing_anchor is not None
            else datetime.combine(day.date, time(21, 0), timezone_info)
        )
        for item in items:
            if item is closing_anchor:
                break
            if item.item_type == ItineraryItemType.ARRIVAL_POINT:
                continue
            gap = item.scheduled_start_at - cursor
            if gap >= timedelta(minutes=SUPPLEMENT_GAP_MINUTES):
                return True
            cursor = max(cursor, item.scheduled_end_at)
        return available_end - cursor >= timedelta(
            minutes=SUPPLEMENT_GAP_MINUTES
        )

    @staticmethod
    def _supplement_recommendation_centers(
        *,
        result: ItineraryResult,
        target_dates: list[date],
    ) -> list[RecommendationCenter]:
        """부족한 날짜에 이미 형성된 동선을 추가 조회 기준점으로 사용한다."""

        target_set = set(target_dates)
        centers: list[RecommendationCenter] = []
        for day in result.days:
            if day.date not in target_set or not day.items:
                continue
            movable_items = [
                item
                for item in day.items
                if item.item_type
                not in {
                    ItineraryItemType.ARRIVAL_POINT,
                    ItineraryItemType.DEPARTURE_POINT,
                }
            ]
            anchor = movable_items[-1] if movable_items else day.items[0]
            centers.append(
                RecommendationCenter(
                    latitude=anchor.latitude,
                    longitude=anchor.longitude,
                )
            )
        return centers

    @staticmethod
    def _merge_recommendation_fetch_diagnostics(
        diagnostics: dict[str, object],
        supplemental: dict[str, object],
    ) -> None:
        for key in ("fetchedCount", "candidateCount", "detailLookupCount"):
            diagnostics[key] = int(diagnostics.get(key, 0)) + int(
                supplemental.get(key, 0)
            )
        for key in ("categoryDistribution", "filteredCounts"):
            combined = Counter(diagnostics.get(key, {}))
            combined.update(supplemental.get(key, {}))
            diagnostics[key] = dict(sorted(combined.items()))
        diagnostics["supplementalFetchCount"] = int(
            supplemental.get("fetchedCount", 0)
        )
        diagnostics["supplementalCandidateCount"] = int(
            supplemental.get("candidateCount", 0)
        )

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
                place_id=trip.accommodation.accommodation_id,
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
                travel_style=trip.travel_style,
                schedule_density=trip.schedule_density,
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

    @staticmethod
    def _recommendation_centers(*, trip, stadium) -> list[RecommendationCenter]:
        """각 날짜의 시작·종료 Anchor 주변에서 추천 후보를 확보합니다."""

        points = [
            stadium,
            trip.arrival_point,
            trip.departure_point,
        ]
        if trip.accommodation is not None:
            points.append(trip.accommodation)
        centers: list[RecommendationCenter] = []
        seen: set[tuple[float, float]] = set()
        for point in points:
            key = (round(point.latitude, 5), round(point.longitude, 5))
            if key in seen:
                continue
            seen.add(key)
            centers.append(
                RecommendationCenter(
                    latitude=point.latitude,
                    longitude=point.longitude,
                )
            )
        return centers

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
            # 원래 예외를 덮어쓰지는 않되 운영자가 고착 상태를 찾을 수 있게
            # 복구 실패 사실과 여행 ID를 반드시 남깁니다.
            logger.exception(
                "일정 생성 실패 후 여행 상태 복구에 실패했습니다: "
                "trip_id=%s target_status=%s",
                trip_id,
                original_status.value,
            )

    def _recover_stale_generation(self, trip: TripRecord) -> TripRecord:
        """인스턴스 종료 등으로 남은 오래된 GENERATING lease를 회수합니다."""

        if trip.status != TripStatus.GENERATING:
            return trip

        now = datetime.now(timezone.utc)
        recovered = self._trip_repository.recover_stale_generation(
            trip_id=trip.trip_id,
            stale_before=now - GENERATION_STALE_AFTER,
            updated_at=now,
        )
        if recovered is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="TRIP_NOT_FOUND",
                message="여행 정보를 찾을 수 없습니다.",
            )
        if recovered.status != TripStatus.GENERATING:
            logger.warning(
                "중단된 일정 생성 상태를 복구했습니다: trip_id=%s "
                "restored_status=%s stale_after_seconds=%s",
                trip.trip_id,
                recovered.status.value,
                int(GENERATION_STALE_AFTER.total_seconds()),
            )
        return recovered

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
            total_travel_distance_meters=(
                result.total_travel_distance_meters
            ),
            days=stored_days,
            excluded_places=result.excluded_places,
            recommendation_summary=result.recommendation_summary,
            created_at=now,
            updated_at=now,
        )

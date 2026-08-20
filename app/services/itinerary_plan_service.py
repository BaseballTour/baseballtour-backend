from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import status

from app.algorithms.itinerary_editor import (
    ItineraryEditError,
    insert_place_item,
    item_node_id,
    recalculate_day_schedule,
    remove_place_item,
    reorder_place_items,
    update_place_item_fixed,
    update_place_item_start,
)
from app.algorithms.itinerary_generator import DEFAULT_DAY_START
from app.algorithms.travel_time import (
    MatrixNode,
    TravelTimeProvider,
    build_travel_time_matrix,
)
from app.core.exceptions import AppException
from app.core.time import KOREA_TIMEZONE
from app.external.odsay.client import get_cached_transit_minutes
from app.external.tour_api.adapter import (
    TourApiAdapter,
    tour_api_adapter,
)
from app.models.itinerary import ItineraryItemAddedBy, ItineraryItemType
from app.repositories.itinerary_plan_repository import (
    ItineraryPlanRepository,
)
from app.repositories.trip_repository import TripRepository
from app.schemas.itinerary_plan import (
    ItineraryPlanAddItemRequest,
    ItineraryPlanFixedRequest,
    ItineraryPlanItem,
    ItineraryPlanRecord,
    ItineraryPlanReorderRequest,
    ItineraryPlanTimeUpdateRequest,
)
from app.schemas.trip import TripRecord, TripStatus


class ItineraryPlanService:
    """생성된 여행 일정 Plan의 조회·삭제·편집을 담당합니다."""

    def __init__(
        self,
        trip_repository: TripRepository | None = None,
        itinerary_plan_repository: ItineraryPlanRepository | None = None,
        travel_time_provider: TravelTimeProvider | None = (
            get_cached_transit_minutes
        ),
        place_adapter: TourApiAdapter | None = None,
    ) -> None:
        self._trip_repository = (
            trip_repository
            or TripRepository()
        )
        self._itinerary_plan_repository = (
            itinerary_plan_repository
            or ItineraryPlanRepository()
        )
        self._travel_time_provider = travel_time_provider
        self._place_adapter = place_adapter or tour_api_adapter

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

    async def reorder_items(
        self,
        *,
        user_id: str,
        trip_id: str,
        request: ItineraryPlanReorderRequest,
    ) -> ItineraryPlanRecord:
        """특정 날짜의 PLACE 항목 순서를 변경합니다."""

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
                    "현재 일정을 수정할 수 없습니다."
                ),
            )

        plan = self._get_active_plan_or_raise(
            trip=trip,
            user_id=user_id,
        )

        day_index = next(
            (
                index
                for index, day in enumerate(plan.days)
                if day.date == request.date
            ),
            None,
        )

        if day_index is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="ITINERARY_DAY_NOT_FOUND",
                message="수정할 날짜의 일정을 찾을 수 없습니다.",
            )

        day = plan.days[day_index]

        try:
            reordered_day = reorder_place_items(
                day,
                request.item_ids,
            )

            (
                start_node_id,
                start_latitude,
                start_longitude,
                day_start_at,
            ) = self._resolve_day_start(
                trip=trip,
                target_date=day.date,
            )

            nodes = [
                MatrixNode(
                    node_id=start_node_id,
                    latitude=start_latitude,
                    longitude=start_longitude,
                )
            ]

            nodes.extend(
                MatrixNode(
                    node_id=item_node_id(item),
                    latitude=item.latitude,
                    longitude=item.longitude,
                )
                for item in reordered_day.items
            )

            matrix = await build_travel_time_matrix(
                nodes,
                provider=self._travel_time_provider,
            )

            recalculated_day = recalculate_day_schedule(
                reordered_day,
                matrix=matrix,
                start_node_id=start_node_id,
                day_start_at=day_start_at,
            )

        except ItineraryEditError as exc:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="ITINERARY_EDIT_INVALID",
                message=str(exc),
            ) from exc

        updated_days = list(plan.days)
        updated_days[day_index] = recalculated_day

        total_travel_minutes = sum(
            item.travel_minutes_from_previous
            for current_day in updated_days
            for item in current_day.items
        )

        updated = (
            self._itinerary_plan_repository.update_schedule(
                plan_id=plan.plan_id,
                days=updated_days,
                total_travel_minutes=total_travel_minutes,
                updated_at=datetime.now(timezone.utc),
            )
        )

        if updated is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="ITINERARY_PLAN_NOT_FOUND",
                message="현재 활성화된 여행 일정을 찾을 수 없습니다.",
            )

        return updated

    async def delete_item(
        self,
        *,
        user_id: str,
        trip_id: str,
        item_id: str,
    ) -> ItineraryPlanRecord:
        """현재 ACTIVE Plan에서 특정 PLACE 항목을 삭제합니다."""

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
                    "현재 일정을 수정할 수 없습니다."
                ),
            )

        plan = self._get_active_plan_or_raise(
            trip=trip,
            user_id=user_id,
        )

        day_index = next(
            (
                index
                for index, day in enumerate(plan.days)
                if any(
                    item.item_id == item_id
                    for item in day.items
                )
            ),
            None,
        )

        if day_index is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="ITINERARY_ITEM_NOT_FOUND",
                message="삭제할 일정 항목을 찾을 수 없습니다.",
            )

        day = plan.days[day_index]

        try:
            removed_day = remove_place_item(
                day,
                item_id,
            )

            (
                start_node_id,
                start_latitude,
                start_longitude,
                day_start_at,
            ) = self._resolve_day_start(
                trip=trip,
                target_date=day.date,
            )

            nodes = [
                MatrixNode(
                    node_id=start_node_id,
                    latitude=start_latitude,
                    longitude=start_longitude,
                )
            ]

            nodes.extend(
                MatrixNode(
                    node_id=item_node_id(item),
                    latitude=item.latitude,
                    longitude=item.longitude,
                )
                for item in removed_day.items
            )

            matrix = await build_travel_time_matrix(
                nodes,
                provider=self._travel_time_provider,
            )

            recalculated_day = recalculate_day_schedule(
                removed_day,
                matrix=matrix,
                start_node_id=start_node_id,
                day_start_at=day_start_at,
            )

        except ItineraryEditError as exc:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="ITINERARY_EDIT_INVALID",
                message=str(exc),
            ) from exc

        updated_days = list(plan.days)
        updated_days[day_index] = recalculated_day

        total_travel_minutes = sum(
            item.travel_minutes_from_previous
            for current_day in updated_days
            for item in current_day.items
        )

        updated = (
            self._itinerary_plan_repository.update_schedule(
                plan_id=plan.plan_id,
                days=updated_days,
                total_travel_minutes=total_travel_minutes,
                updated_at=datetime.now(timezone.utc),
            )
        )

        if updated is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="ITINERARY_PLAN_NOT_FOUND",
                message="현재 활성화된 여행 일정을 찾을 수 없습니다.",
            )

        return updated

    async def add_item(
        self,
        *,
        user_id: str,
        trip_id: str,
        request: ItineraryPlanAddItemRequest,
    ) -> ItineraryPlanRecord:
        """현재 ACTIVE Plan의 특정 날짜에 PLACE를 추가합니다."""

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
                    "현재 일정을 수정할 수 없습니다."
                ),
            )

        plan = self._get_active_plan_or_raise(
            trip=trip,
            user_id=user_id,
        )

        day_index = next(
            (
                index
                for index, day in enumerate(plan.days)
                if day.date == request.date
            ),
            None,
        )

        if day_index is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="ITINERARY_DAY_NOT_FOUND",
                message="장소를 추가할 날짜의 일정을 찾을 수 없습니다.",
            )

        if (
            not request.place_id.startswith("tour_")
            or not request.place_id.removeprefix("tour_")
        ):
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="ITINERARY_PLACE_ID_INVALID",
                message=(
                    "일정에 추가할 장소 ID는 "
                    "tour_{contentId} 형식이어야 합니다."
                ),
            )

        day = plan.days[day_index]

        if any(
            item.item_type == ItineraryItemType.PLACE
            and item.place_id == request.place_id
            for item in day.items
        ):
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="ITINERARY_PLACE_ALREADY_EXISTS",
                message="해당 장소가 이미 일정에 포함되어 있습니다.",
            )

        content_id = request.place_id.removeprefix(
            "tour_"
        )

        try:
            place = await self._place_adapter.get_place_detail(
                content_id
            )
        except ValueError as exc:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="ITINERARY_PLACE_NOT_FOUND",
                message="추가할 장소 정보를 찾을 수 없습니다.",
            ) from exc

        (
            start_node_id,
            start_latitude,
            start_longitude,
            day_start_at,
        ) = self._resolve_day_start(
            trip=trip,
            target_date=day.date,
        )

        stay_minutes = max(
            1,
            place.default_stay_minutes,
        )

        new_item = ItineraryPlanItem(
            item_id=f"item_{uuid4().hex}",
            type=ItineraryItemType.PLACE,
            sequence=len(day.items) + 1,
            place_id=request.place_id,
            category=getattr(place, "category", None),
            name=place.name,
            address=place.address or place.name,
            latitude=place.latitude,
            longitude=place.longitude,
            scheduled_start_at=day_start_at,
            scheduled_end_at=(
                day_start_at
                + timedelta(minutes=stay_minutes)
            ),
            travel_minutes_from_previous=0,
            travel_time_source=None,
            is_required=request.is_required,
            added_by=ItineraryItemAddedBy.USER,
        )

        try:
            inserted_day = insert_place_item(
                day,
                new_item,
            )

            nodes = [
                MatrixNode(
                    node_id=start_node_id,
                    latitude=start_latitude,
                    longitude=start_longitude,
                )
            ]

            nodes.extend(
                MatrixNode(
                    node_id=item_node_id(item),
                    latitude=item.latitude,
                    longitude=item.longitude,
                )
                for item in inserted_day.items
            )

            matrix = await build_travel_time_matrix(
                nodes,
                provider=self._travel_time_provider,
            )

            recalculated_day = recalculate_day_schedule(
                inserted_day,
                matrix=matrix,
                start_node_id=start_node_id,
                day_start_at=day_start_at,
            )

        except ItineraryEditError as exc:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="ITINERARY_EDIT_INVALID",
                message=str(exc),
            ) from exc

        updated_days = list(plan.days)
        updated_days[day_index] = recalculated_day

        total_travel_minutes = sum(
            item.travel_minutes_from_previous
            for current_day in updated_days
            for item in current_day.items
        )

        updated = (
            self._itinerary_plan_repository.update_schedule(
                plan_id=plan.plan_id,
                days=updated_days,
                total_travel_minutes=total_travel_minutes,
                updated_at=datetime.now(timezone.utc),
            )
        )

        if updated is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="ITINERARY_PLAN_NOT_FOUND",
                message="현재 활성화된 여행 일정을 찾을 수 없습니다.",
            )

        return updated

    async def update_item_fixed(
        self,
        *,
        user_id: str,
        trip_id: str,
        item_id: str,
        request: ItineraryPlanFixedRequest,
    ) -> ItineraryPlanRecord:
        """PLACE 항목의 재생성 고정 여부를 변경합니다."""

        trip, plan, day_index = self._editable_item_context(
            user_id=user_id,
            trip_id=trip_id,
            item_id=item_id,
        )
        try:
            updated_day = update_place_item_fixed(
                plan.days[day_index], item_id, request.is_fixed
            )
        except ItineraryEditError as exc:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="ITINERARY_EDIT_INVALID",
                message=str(exc),
            ) from exc
        return self._save_updated_day(plan, day_index, updated_day)

    async def update_item_time(
        self,
        *,
        user_id: str,
        trip_id: str,
        item_id: str,
        request: ItineraryPlanTimeUpdateRequest,
    ) -> ItineraryPlanRecord:
        """PLACE 시작시간을 수정하고 앞뒤 시간표를 재계산합니다."""

        trip, plan, day_index = self._editable_item_context(
            user_id=user_id,
            trip_id=trip_id,
            item_id=item_id,
        )
        day = plan.days[day_index]
        try:
            changed = update_place_item_start(
                day, item_id, request.scheduled_start_at
            )
            recalculated = await self._recalculate_day(
                trip=trip,
                day=changed,
            )
        except ItineraryEditError as exc:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="ITINERARY_EDIT_INVALID",
                message=str(exc),
            ) from exc
        return self._save_updated_day(plan, day_index, recalculated)

    def _editable_item_context(
        self,
        *,
        user_id: str,
        trip_id: str,
        item_id: str,
    ):
        trip = self._get_owned_trip_or_raise(user_id=user_id, trip_id=trip_id)
        if trip.status == TripStatus.GENERATING:
            raise AppException(
                status_code=status.HTTP_409_CONFLICT,
                code="TRIP_GENERATION_IN_PROGRESS",
                message="일정 생성 중에는 현재 일정을 수정할 수 없습니다.",
            )
        plan = self._get_active_plan_or_raise(trip=trip, user_id=user_id)
        day_index = next(
            (
                index
                for index, day in enumerate(plan.days)
                if any(item.item_id == item_id for item in day.items)
            ),
            None,
        )
        if day_index is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="ITINERARY_ITEM_NOT_FOUND",
                message="수정할 일정 항목을 찾을 수 없습니다.",
            )
        return trip, plan, day_index

    async def _recalculate_day(
        self,
        *,
        trip: TripRecord,
        day,
    ):
        start_node_id, latitude, longitude, day_start_at = (
            self._resolve_day_start(trip=trip, target_date=day.date)
        )
        nodes = [MatrixNode(start_node_id, latitude, longitude)]
        nodes.extend(
            MatrixNode(item_node_id(item), item.latitude, item.longitude)
            for item in day.items
        )
        matrix = await build_travel_time_matrix(
            nodes,
            provider=self._travel_time_provider,
        )
        return recalculate_day_schedule(
            day,
            matrix=matrix,
            start_node_id=start_node_id,
            day_start_at=day_start_at,
        )

    def _save_updated_day(self, plan, day_index: int, day):
        days = list(plan.days)
        days[day_index] = day
        total = sum(
            item.travel_minutes_from_previous
            for current_day in days
            for item in current_day.items
        )
        updated = self._itinerary_plan_repository.update_schedule(
            plan_id=plan.plan_id,
            days=days,
            total_travel_minutes=total,
            updated_at=datetime.now(timezone.utc),
        )
        if updated is None:
            raise AppException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="ITINERARY_PLAN_NOT_FOUND",
                message="현재 활성화된 여행 일정을 찾을 수 없습니다.",
            )
        return updated

    def _resolve_day_start(
        self,
        *,
        trip: TripRecord,
        target_date,
    ) -> tuple[str, float, float, datetime]:
        """해당 날짜의 일정 계산 시작 지점과 시간을 결정합니다."""

        trip_start_at = trip.trip_start_at.astimezone(
            KOREA_TIMEZONE
        )
        timezone_info = KOREA_TIMEZONE

        if timezone_info is None:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="ITINERARY_INPUT_INVALID",
                message="여행 시간에는 timezone 정보가 필요합니다.",
            )

        if trip.arrival_point is None:
            raise AppException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="TRIP_POINTS_REQUIRED",
                message="일정 수정을 위해 도착 장소가 필요합니다.",
            )

        if target_date == trip_start_at.date():
            return (
                "arrival",
                trip.arrival_point.latitude,
                trip.arrival_point.longitude,
                trip_start_at,
            )

        day_start_at = datetime.combine(
            target_date,
            DEFAULT_DAY_START,
            timezone_info,
        )

        if trip.accommodation is not None:
            return (
                "accommodation",
                trip.accommodation.latitude,
                trip.accommodation.longitude,
                day_start_at,
            )

        return (
            "arrival",
            trip.arrival_point.latitude,
            trip.arrival_point.longitude,
            day_start_at,
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

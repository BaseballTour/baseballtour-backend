from __future__ import annotations

import asyncio
import logging
import math
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from app.external.tour_api.adapter import TourApiAdapter, tour_api_adapter
from app.models.place import (
    BusinessRuleStatus,
    Place,
    PlaceCategory,
    PlaceSource,
)


logger = logging.getLogger(__name__)

DEFAULT_RECOMMENDATION_RADIUS_METERS = 10_000
DEFAULT_RECOMMENDATION_PAGE_SIZE = 20
DEFAULT_MAX_PAGES_PER_CENTER = 2
DEFAULT_MAX_CANDIDATES = 12
DETAIL_CONCURRENCY = 5
NEARBY_PAGE_TIMEOUT_SECONDS = 6.0
DETAIL_TIMEOUT_SECONDS = 5.0
DINING_CATEGORY_MINIMUM = 2
CATEGORY_MAXIMUMS = {
    PlaceCategory.RESTAURANT: 4,
    PlaceCategory.CAFE: 2,
    PlaceCategory.SHOPPING: 2,
    PlaceCategory.FESTIVAL: 1,
    PlaceCategory.TOURIST_SPOT: 4,
    PlaceCategory.CULTURAL_FACILITY: 4,
    PlaceCategory.ACTIVITY: 3,
    PlaceCategory.OTHER: 1,
}


@dataclass(frozen=True)
class RecommendationCenter:
    """TourAPI 위치 기반 추천 조회의 기준점."""

    latitude: float
    longitude: float


@dataclass(frozen=True)
class ExcludedRecommendationPlace:
    """자동 추천에서 제외할 Anchor 장소 정보."""

    name: str
    latitude: float
    longitude: float


class RecommendationService:
    """TourAPI 장소를 일정 자동 채우기 후보로 준비합니다."""

    def __init__(
        self,
        place_adapter: TourApiAdapter | None = None,
        *,
        radius: int = DEFAULT_RECOMMENDATION_RADIUS_METERS,
        page_size: int = DEFAULT_RECOMMENDATION_PAGE_SIZE,
        max_pages_per_center: int = DEFAULT_MAX_PAGES_PER_CENTER,
        max_candidates: int = DEFAULT_MAX_CANDIDATES,
    ) -> None:
        self._place_adapter = place_adapter or tour_api_adapter
        self._radius = radius
        self._page_size = page_size
        self._max_pages_per_center = max_pages_per_center
        self._max_candidates = max_candidates

    async def get_candidates(
        self,
        *,
        centers: Iterable[RecommendationCenter],
        selected_place_ids: Iterable[str] = (),
        excluded_places: Iterable[ExcludedRecommendationPlace] = (),
        travel_start_date: date | None = None,
        travel_end_date: date | None = None,
        diagnostics: dict[str, object] | None = None,
    ) -> list[Place]:
        """기준점 주변의 중복되지 않은 TourAPI 추천 후보를 반환합니다."""

        selected_ids = set(selected_place_ids)
        excluded_anchors = tuple(excluded_places)
        nearby_places: list[Place] = []
        rejected: Counter[str] = Counter()

        center_results = await asyncio.gather(
            *(
                self._load_all_nearby_pages(center)
                for center in _deduplicate_centers(centers)
            )
        )
        if center_results and all(failed for _, failed in center_results):
            raise asyncio.TimeoutError(
                "모든 추천 기준점의 TourAPI 조회에 실패했습니다."
            )

        for places, _ in center_results:
            nearby_places.extend(places)

        eligible = _filter_and_deduplicate(
            nearby_places,
            excluded_ids=selected_ids,
            excluded_places=excluded_anchors,
            rejected=rejected,
        )
        source_categories = Counter(
            _enum_value(place.category) for place in eligible
        )
        filtered = _select_diverse_candidates(
            eligible,
            max_candidates=self._max_candidates,
            rejected=rejected,
        )
        detailed = await self._resolve_details(filtered)
        available = sorted(
            (
                place
                for place in detailed
                if _is_available_during_trip(
                    place,
                    travel_start_date=travel_start_date,
                    travel_end_date=travel_end_date,
                )
            ),
            key=_recommendation_sort_key,
        )
        rejected["UNVERIFIED_FESTIVAL"] += len(filtered) - len(detailed)
        rejected["OUTSIDE_EVENT_PERIOD"] += len(detailed) - len(available)
        hours_statuses = Counter(
            _enum_value(place.business_hours_status) for place in available
        )
        missing_categories = [
            category.value
            for category in (
                PlaceCategory.RESTAURANT,
                PlaceCategory.CAFE,
                PlaceCategory.SHOPPING,
                PlaceCategory.TOURIST_SPOT,
                PlaceCategory.CULTURAL_FACILITY,
                PlaceCategory.ACTIVITY,
            )
            if source_categories[category.value] == 0
        ]
        logger.info(
            "자동 추천 후보 진단: fetched=%s selected=%s detailed=%s "
            "available=%s rejected=%s categories=%s",
            len(nearby_places),
            len(filtered),
            len(detailed),
            len(available),
            dict(sorted(rejected.items())),
            dict(sorted(Counter(str(item.category) for item in available).items())),
        )
        if diagnostics is not None:
            diagnostics.update(
                {
                    "fetchedCount": len(nearby_places),
                    "candidateCount": len(available),
                    "categoryDistribution": dict(
                        sorted(
                            Counter(str(item.category) for item in available).items()
                        )
                    ),
                    "sourceCategoryDistribution": dict(
                        sorted(source_categories.items())
                    ),
                    "missingSourceCategories": missing_categories,
                    "businessHoursStatusDistribution": dict(
                        sorted(hours_statuses.items())
                    ),
                    "detailLookupCount": len(filtered),
                    "filteredCounts": dict(sorted(rejected.items())),
                }
            )
        return available

    async def _load_all_nearby_pages(
        self,
        center: RecommendationCenter,
    ) -> tuple[list[Place], bool]:
        places: list[Place] = []
        page_no = 1
        first_page_failed = False

        while page_no <= self._max_pages_per_center:
            try:
                page = await asyncio.wait_for(
                    self._place_adapter.get_nearby_place_page(
                        longitude=center.longitude,
                        latitude=center.latitude,
                        radius=self._radius,
                        page_no=page_no,
                        num_of_rows=self._page_size,
                    ),
                    timeout=NEARBY_PAGE_TIMEOUT_SECONDS,
                )
            except Exception as exc:
                # 추천 실패는 사용자가 선택한 장소의 일정 생성을 막지 않습니다.
                logger.warning(
                    "TourAPI 추천 후보 조회를 건너뜁니다: page=%s reason=%s",
                    page_no,
                    exc,
                )
                first_page_failed = page_no == 1
                break

            places.extend(page.places)

            if page.next_page_token is None:
                break

            try:
                next_page = int(page.next_page_token)
            except (TypeError, ValueError):
                break

            if next_page <= page_no:
                break
            page_no = next_page

        return places, first_page_failed

    async def _resolve_details(self, places: list[Place]) -> list[Place]:
        semaphore = asyncio.Semaphore(DETAIL_CONCURRENCY)

        async def resolve(place: Place) -> Place:
            content_id = place.source_content_id
            if not content_id:
                return place

            try:
                async with semaphore:
                    detailed = await asyncio.wait_for(
                        self._place_adapter.get_place_detail(content_id),
                        timeout=DETAIL_TIMEOUT_SECONDS,
                    )
            except Exception as exc:
                logger.info(
                    "TourAPI 추천 상세정보를 주변 조회 값으로 대체합니다: "
                    "place_id=%s reason=%s",
                    place.place_id,
                    exc,
                )
                return place

            # 상세 API에는 기준점 거리가 없으므로 주변 조회의 거리를 유지합니다.
            return detailed.model_copy(
                update={"distance_meters": place.distance_meters}
            )

        resolved = await asyncio.gather(*(resolve(place) for place in places))

        return [
            place
            for place in resolved
            if not (
                place.category == PlaceCategory.FESTIVAL
                and place.business_hours_status
                != BusinessRuleStatus.PARSED
            )
        ]


def _deduplicate_centers(
    centers: Iterable[RecommendationCenter],
) -> list[RecommendationCenter]:
    unique: dict[tuple[float, float], RecommendationCenter] = {}
    for center in centers:
        key = (round(center.latitude, 6), round(center.longitude, 6))
        unique.setdefault(key, center)
    return list(unique.values())


def _filter_and_deduplicate(
    places: Iterable[Place],
    *,
    excluded_ids: set[str],
    excluded_places: tuple[ExcludedRecommendationPlace, ...] = (),
    rejected: Counter[str] | None = None,
) -> list[Place]:
    unique: dict[str, Place] = {}

    for place in places:
        if place.place_id in excluded_ids:
            if rejected is not None:
                rejected["ALREADY_SELECTED_OR_REJECTED"] += 1
            continue
        if any(
            _matches_excluded_place(place, excluded)
            for excluded in excluded_places
        ):
            if rejected is not None:
                rejected["ANCHOR_DUPLICATE"] += 1
            continue
        if place.source != PlaceSource.TOUR_API:
            if rejected is not None:
                rejected["UNSUPPORTED_SOURCE"] += 1
            continue
        if place.category == PlaceCategory.ACCOMMODATION:
            if rejected is not None:
                rejected["ACCOMMODATION"] += 1
            continue
        if (place.lcls_system2 or "").startswith("VE10"):
            if rejected is not None:
                rejected["SPORTS_FACILITY"] += 1
            continue

        current = unique.get(place.place_id)
        if current is None or _distance(place) < _distance(current):
            if current is not None and rejected is not None:
                rejected["DUPLICATE_PLACE"] += 1
            unique[place.place_id] = place
        elif rejected is not None:
            rejected["DUPLICATE_PLACE"] += 1

    return list(unique.values())


def _matches_excluded_place(
    place: Place,
    excluded: ExcludedRecommendationPlace,
) -> bool:
    """이름이 같거나 좌표가 사실상 동일한 Anchor 후보를 제외한다."""

    if _normalize_place_name(place.name) == _normalize_place_name(
        excluded.name
    ):
        return True

    return _coordinate_distance_meters(
        place.latitude,
        place.longitude,
        excluded.latitude,
        excluded.longitude,
    ) <= 30


def _normalize_place_name(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", value.casefold())


def _coordinate_distance_meters(
    latitude1: float,
    longitude1: float,
    latitude2: float,
    longitude2: float,
) -> float:
    radius_meters = 6_371_000
    lat1 = math.radians(latitude1)
    lat2 = math.radians(latitude2)
    delta_lat = math.radians(latitude2 - latitude1)
    delta_lon = math.radians(longitude2 - longitude1)
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(delta_lon / 2) ** 2
    )
    return radius_meters * 2 * math.atan2(
        math.sqrt(haversine),
        math.sqrt(1 - haversine),
    )


def _select_diverse_candidates(
    places: list[Place],
    *,
    max_candidates: int,
    rejected: Counter[str] | None = None,
) -> list[Place]:
    """원천에 존재하는 카테고리를 순환 선별하고 부족분은 거리순으로 채운다."""
    ordered = sorted(places, key=_recommendation_sort_key)
    selected: list[Place] = []
    selected_ids: set[str] = set()

    for category in (PlaceCategory.RESTAURANT, PlaceCategory.CAFE):
        for place in (
            item for item in ordered if item.category == category
        ):
            if len(selected) >= max_candidates:
                break
            selected.append(place)
            selected_ids.add(place.place_id)
            if sum(
                item.category == category for item in selected
            ) >= DINING_CATEGORY_MINIMUM:
                break

    category_order = sorted(
        {place.category for place in ordered},
        key=lambda category: CATEGORY_PRIORITY.get(category, 99),
    )
    category_queues = {
        category: [
            place
            for place in ordered
            if place.category == category and place.place_id not in selected_ids
        ]
        for category in category_order
    }
    category_counts = Counter(place.category for place in selected)

    made_progress = True
    while len(selected) < max_candidates and made_progress:
        made_progress = False
        for category in category_order:
            queue = category_queues[category]
            maximum = CATEGORY_MAXIMUMS.get(category, max_candidates)
            if not queue or category_counts[category] >= maximum:
                continue
            place = queue.pop(0)
            selected.append(place)
            selected_ids.add(place.place_id)
            category_counts[category] += 1
            made_progress = True
            if len(selected) >= max_candidates:
                break

    # 소분류가 없는 지역도 후보 수 자체가 줄지 않도록 soft cap을 완화합니다.
    for place in ordered:
        if len(selected) >= max_candidates:
            break
        if place.place_id in selected_ids:
            continue
        selected.append(place)
        selected_ids.add(place.place_id)
        if rejected is not None:
            rejected["CATEGORY_LIMIT_RELAXED"] += 1

    if rejected is not None and len(selected) >= max_candidates:
        rejected["CANDIDATE_LIMIT"] += max(0, len(ordered) - len(selected))
    return sorted(selected, key=_recommendation_sort_key)


def _is_available_during_trip(
    place: Place,
    *,
    travel_start_date: date | None,
    travel_end_date: date | None,
) -> bool:
    if place.category != PlaceCategory.FESTIVAL:
        return True
    if travel_start_date is None or travel_end_date is None:
        return True
    if place.event_end_date is not None and place.event_end_date < travel_start_date:
        return False
    if place.event_start_date is not None and place.event_start_date > travel_end_date:
        return False
    return True


CATEGORY_PRIORITY = {
    PlaceCategory.TOURIST_SPOT: 0,
    PlaceCategory.CULTURAL_FACILITY: 1,
    PlaceCategory.RESTAURANT: 2,
    PlaceCategory.CAFE: 3,
    PlaceCategory.SHOPPING: 4,
    PlaceCategory.ACTIVITY: 5,
    PlaceCategory.FESTIVAL: 6,
    PlaceCategory.OTHER: 7,
}


def _distance(place: Place) -> float:
    return (
        place.distance_meters
        if place.distance_meters is not None
        else float("inf")
    )


def _enum_value(value: object) -> str:
    return str(getattr(value, "value", value))


def _recommendation_sort_key(place: Place) -> tuple[float, int, str]:
    return (
        _distance(place),
        CATEGORY_PRIORITY.get(place.category, 99),
        place.place_id,
    )

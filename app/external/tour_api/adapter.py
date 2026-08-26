from __future__ import annotations

import asyncio
from datetime import datetime
from dataclasses import dataclass, field
from time import monotonic
from typing import Any, Awaitable, Callable

import httpx

from app.external.tour_api.client import (
    extract_items,
    get_nearby_places,
    get_classification_codes,
    get_place_common_info,
    get_place_images,
    get_place_intro_info,
    search_places_by_keyword,
)
from app.external.tour_api.mapper import (
    deduplicate_places,
    empty_string_to_none,
    get_tour_api_content_type_id,
    tour_api_item_to_place,
    tour_api_items_to_places,
)
from app.models.place import Place, PlaceCategory
from app.schemas.tour import TourClassification
from app.external.tour_api.business_hours import (
    parse_admission_deadline,
    parse_business_hours,
    parse_closed_days,
)


DEFAULT_CACHE_TTL_SECONDS = 300


@dataclass
class _CacheEntry:
    expires_at: float
    value: Any


@dataclass(frozen=True)
class NearbyPlacePage:
    places: list[Place]
    next_page_token: str | None


@dataclass(frozen=True)
class ClassificationPage:
    classifications: list[TourClassification]
    next_page_token: str | None


@dataclass
class TourApiAdapter:
    """TourAPI 원시 응답을 캐시하고 내부 Place로 조합한다."""

    cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS
    _cache: dict[tuple[Any, ...], _CacheEntry] = field(
        default_factory=dict
    )

    async def _cached(
        self,
        key: tuple[Any, ...],
        loader: Callable[[], Awaitable[Any]],
    ) -> Any:
        entry = self._cache.get(key)
        now = monotonic()
        if entry is not None and entry.expires_at > now:
            return entry.value

        value = await loader()
        self._cache[key] = _CacheEntry(
            expires_at=now + self.cache_ttl_seconds,
            value=value,
        )
        return value

    async def get_nearby_place_page(
        self,
        longitude: float,
        latitude: float,
        radius: int = 2000,
        page_no: int = 1,
        num_of_rows: int = 20,
        category: PlaceCategory | None = None,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> NearbyPlacePage:
        content_type_id = get_tour_api_content_type_id(
            category
        )

        if (
            category is not None
            and content_type_id is None
        ):
            return NearbyPlacePage(
                places=[],
                next_page_token=None,
            )

        key = (
            "nearby",
            longitude,
            latitude,
            radius,
            category.value
            if category is not None
            else None,
            page_no,
            num_of_rows,
        )

        async def load() -> NearbyPlacePage:
            raw = await get_nearby_places(
                longitude=longitude,
                latitude=latitude,
                radius=radius,
                page_no=page_no,
                num_of_rows=num_of_rows,
                content_type_id=content_type_id,
                client=client,
            )

            raw_items = extract_items(raw)

            places = deduplicate_places(
                tour_api_items_to_places(
                    raw_items
                )
            )

            body = (
                raw.get("response", {})
                .get("body", {})
            )

            total_count: int | None = None

            if isinstance(body, dict):
                try:
                    total_count = int(
                        body.get("totalCount")
                    )
                except (TypeError, ValueError):
                    total_count = None

            if total_count is not None:
                has_next = (
                    page_no * num_of_rows
                    < total_count
                )
            else:
                has_next = (
                    len(raw_items)
                    == num_of_rows
                )

            return NearbyPlacePage(
                places=places,
                next_page_token=(
                    str(page_no + 1)
                    if has_next
                    else None
                ),
            )

        return await self._cached(
            key,
            load,
        )

    async def get_nearby_place_list(
        self,
        longitude: float,
        latitude: float,
        radius: int = 2000,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> list[Place]:
        page = await self.get_nearby_place_page(
            longitude=longitude,
            latitude=latitude,
            radius=radius,
            client=client,
        )

        return page.places

    async def search_place_page(
        self,
        keyword: str,
        page_no: int = 1,
        num_of_rows: int = 20,
        category: PlaceCategory | None = None,
        *,
        lcls_system1: str | None = None,
        lcls_system2: str | None = None,
        lcls_system3: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> NearbyPlacePage:
        normalized_keyword = keyword.strip()
        content_type_id = get_tour_api_content_type_id(category)
        if category is not None and content_type_id is None:
            return NearbyPlacePage([], None)
        key = (
            "keyword",
            normalized_keyword,
            category.value if category is not None else None,
            lcls_system1,
            lcls_system2,
            lcls_system3,
            page_no,
            num_of_rows,
        )

        async def load() -> NearbyPlacePage:
            raw = await search_places_by_keyword(
                normalized_keyword,
                page_no=page_no,
                num_of_rows=num_of_rows,
                content_type_id=content_type_id,
                lcls_system1=lcls_system1,
                lcls_system2=lcls_system2,
                lcls_system3=lcls_system3,
                client=client,
            )
            raw_items = extract_items(raw)
            places = deduplicate_places(tour_api_items_to_places(raw_items))
            body = raw.get("response", {}).get("body", {})
            try:
                total_count = int(body.get("totalCount"))
            except (AttributeError, TypeError, ValueError):
                total_count = None
            has_next = (
                page_no * num_of_rows < total_count
                if total_count is not None
                else len(raw_items) == num_of_rows
            )
            return NearbyPlacePage(
                places,
                str(page_no + 1) if has_next else None,
            )

        return await self._cached(key, load)

    async def get_classification_page(
        self,
        page_no: int = 1,
        num_of_rows: int = 100,
        *,
        lcls_system1: str | None = None,
        lcls_system2: str | None = None,
        lcls_system3: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> ClassificationPage:
        key = (
            "classification",
            lcls_system1,
            lcls_system2,
            lcls_system3,
            page_no,
            num_of_rows,
        )

        async def load() -> ClassificationPage:
            raw = await get_classification_codes(
                page_no=page_no,
                num_of_rows=num_of_rows,
                lcls_system1=lcls_system1,
                lcls_system2=lcls_system2,
                lcls_system3=lcls_system3,
                client=client,
            )
            items = extract_items(raw)
            classifications = [
                TourClassification(
                    lcls_system1=str(
                        item.get("lclsSystm1") or ""
                    ).strip(),
                    lcls_system1_name=str(
                        item.get("lclsSystm1Nm") or ""
                    ).strip(),
                    lcls_system2=empty_string_to_none(
                        item.get("lclsSystm2")
                    ),
                    lcls_system2_name=empty_string_to_none(
                        item.get("lclsSystm2Nm")
                    ),
                    lcls_system3=empty_string_to_none(
                        item.get("lclsSystm3")
                    ),
                    lcls_system3_name=empty_string_to_none(
                        item.get("lclsSystm3Nm")
                    ),
                )
                for item in items
                if str(item.get("lclsSystm1") or "").strip()
                and str(item.get("lclsSystm1Nm") or "").strip()
            ]
            body = raw.get("response", {}).get("body", {})
            try:
                total_count = int(body.get("totalCount"))
            except (AttributeError, TypeError, ValueError):
                total_count = None
            has_next = (
                page_no * num_of_rows < total_count
                if total_count is not None
                else len(items) == num_of_rows
            )
            return ClassificationPage(
                classifications=classifications,
                next_page_token=str(page_no + 1) if has_next else None,
            )

        return await self._cached(key, load)

    async def get_place_detail(
        self,
        content_id: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> Place:
        key = ("detail", content_id)

        async def load() -> Place:
            common = await get_place_common_info(
                content_id,
                client=client,
            )
            common_items = extract_items(common)
            if not common_items:
                raise ValueError("TourAPI 장소 상세정보가 없습니다.")

            merged = dict(common_items[0])
            content_type_id = empty_string_to_none(
                merged.get("contenttypeid")
            )

            if content_type_id is not None:
                intro, images = await asyncio.gather(
                    get_place_intro_info(
                        content_id,
                        content_type_id,
                        client=client,
                    ),
                    get_place_images(content_id, client=client),
                )
                intro_items = extract_items(intro)
                if intro_items:
                    merged.update(_normalize_intro(intro_items[0]))
            else:
                images = await get_place_images(
                    content_id,
                    client=client,
                )

            if not empty_string_to_none(merged.get("firstimage")):
                image_items = extract_items(images)
                merged["firstimage"] = _first_image_url(image_items)

            return tour_api_item_to_place(merged)

        return await self._cached(key, load)


def _first_non_empty(
    item: dict[str, Any],
    keys: tuple[str, ...],
) -> str | None:
    for key in keys:
        value = empty_string_to_none(item.get(key))
        if value is not None:
            return value
    return None


def _normalize_intro(item: dict[str, Any]) -> dict[str, Any]:
    """콘텐츠 유형별로 다른 상세 필드를 공통 fallback 필드로 변환한다."""
    hours = _first_non_empty(
        item,
        (
            "opentimefood",
            "opentime",
            "usetime",
            "usetimeculture",
            "usetimeleports",
            "playtime",
        ),
    )
    hours_status, hours_text, hours_rules = parse_business_hours(hours)
    admission_status, admission_text, admission_time = parse_admission_deadline(hours)
    closed_raw = _first_non_empty(item, ("restdatefood", "restdateshopping", "restdateculture", "restdateleports", "restdate"))
    closed_status, closed_text, closed_weekdays = parse_closed_days(closed_raw)
    opening = hours_rules[0].open_time if len(hours_rules) == 1 else None
    closing = hours_rules[0].close_time if len(hours_rules) == 1 else None
    return {
        "openTime": opening or _first_non_empty(item, ("checkintime",)),
        "closeTime": closing or _first_non_empty(item, ("checkouttime",)),
        "businessHoursStatus": hours_status,
        "businessHoursText": hours_text,
        "businessHoursRules": [rule.model_dump() for rule in hours_rules],
        "admissionDeadlineTime": admission_time,
        "admissionDeadlineStatus": admission_status,
        "admissionDeadlineText": admission_text,
        "closedDaysText": closed_text,
        "closedDaysStatus": closed_status,
        "closedWeekdays": closed_weekdays,
        "eventStartDate": _normalize_event_date(item.get("eventstartdate")),
        "eventEndDate": _normalize_event_date(item.get("eventenddate")),
    }


def _normalize_event_date(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y%m%d").date().isoformat()
    except ValueError:
        return None


def _first_image_url(items: list[dict[str, Any]]) -> str | None:
    for item in items:
        value = _first_non_empty(
            item,
            ("originimgurl", "smallimageurl"),
        )
        if value is not None:
            return value
    return None


tour_api_adapter = TourApiAdapter()

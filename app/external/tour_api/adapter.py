from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import re
from time import monotonic
from typing import Any, Awaitable, Callable

import httpx

from app.external.tour_api.client import (
    extract_items,
    get_nearby_places,
    get_place_common_info,
    get_place_images,
    get_place_intro_info,
)
from app.external.tour_api.mapper import (
    deduplicate_places,
    empty_string_to_none,
    tour_api_item_to_place,
    tour_api_items_to_places,
)
from app.models.place import Place


DEFAULT_CACHE_TTL_SECONDS = 300


@dataclass
class _CacheEntry:
    expires_at: float
    value: Any


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

    async def get_nearby_place_list(
        self,
        longitude: float,
        latitude: float,
        radius: int = 2000,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> list[Place]:
        key = ("nearby", longitude, latitude, radius)

        async def load() -> list[Place]:
            raw = await get_nearby_places(
                longitude=longitude,
                latitude=latitude,
                radius=radius,
                client=client,
            )
            places = tour_api_items_to_places(extract_items(raw))
            return deduplicate_places(places)

        return await self._cached(key, load)

    async def get_place_detail(
        self,
        content_id: str,
        content_type_id: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> Place:
        key = ("detail", content_id, content_type_id)

        async def load() -> Place:
            common, intro, images = await asyncio.gather(
                get_place_common_info(content_id, client=client),
                get_place_intro_info(
                    content_id,
                    content_type_id,
                    client=client,
                ),
                get_place_images(content_id, client=client),
            )
            common_items = extract_items(common)
            if not common_items:
                raise ValueError("TourAPI 장소 상세정보가 없습니다.")

            merged = dict(common_items[0])
            intro_items = extract_items(intro)
            if intro_items:
                merged.update(_normalize_intro(intro_items[0]))

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
    opening, closing = _split_hours(hours)
    return {
        "openTime": opening or _first_non_empty(item, ("checkintime",)),
        "closeTime": closing or _first_non_empty(item, ("checkouttime",)),
        "closedDaysText": _first_non_empty(
            item,
            (
                "restdatefood",
                "restdateshopping",
                "restdateculture",
                "restdateleports",
                "restdate",
            ),
        ),
    }


def _split_hours(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    matches = re.findall(r"\b(\d{1,2}):([0-5]\d)\b", value)
    normalized = [f"{int(hour):02d}:{minute}" for hour, minute in matches]
    if not normalized:
        return None, None
    return normalized[0], normalized[-1] if len(normalized) > 1 else None


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

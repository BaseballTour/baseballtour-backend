from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
import logging
import re
from typing import Any, Awaitable, Callable

import httpx

from app.core.exceptions import AppException
from app.external.kakao.client import search_places_by_keyword
from app.external.kakao.mapper import (
    kakao_address,
    kakao_category_to_place_category,
)
from app.models.place import Place, PlaceCategory, PlaceSource


logger = logging.getLogger(__name__)
MAX_MATCH_DISTANCE_METERS = 200


def needs_kakao_enrichment(place: Place) -> bool:
    return (
        not place.address.strip()
        or not place.telephone
        or place.category == PlaceCategory.OTHER
    )


def _normalize_name(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", value.casefold())


def _distance_meters(
    latitude1: float,
    longitude1: float,
    latitude2: float,
    longitude2: float,
) -> float:
    earth_radius = 6_371_000
    lat1, lat2 = radians(latitude1), radians(latitude2)
    delta_lat = lat2 - lat1
    delta_lon = radians(longitude2 - longitude1)
    value = (
        sin(delta_lat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    )
    return 2 * earth_radius * asin(sqrt(value))


def _is_matching_candidate(place: Place, item: dict[str, Any]) -> bool:
    place_name = _normalize_name(place.name)
    candidate_name = _normalize_name(str(item.get("place_name") or ""))
    if not place_name or not candidate_name:
        return False
    if place_name not in candidate_name and candidate_name not in place_name:
        return False

    try:
        longitude = float(item["x"])
        latitude = float(item["y"])
    except (KeyError, TypeError, ValueError):
        return False
    if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
        return False

    return _distance_meters(
        place.latitude,
        place.longitude,
        latitude,
        longitude,
    ) <= MAX_MATCH_DISTANCE_METERS


def _merge_kakao_fields(place: Place, item: dict[str, Any]) -> Place:
    category = kakao_category_to_place_category(
        item.get("category_group_code")
    )
    updates: dict[str, Any] = {
        "kakao_place_id": str(item.get("id") or "").strip() or None,
        "enriched_by": [*place.enriched_by, PlaceSource.KAKAO],
    }
    if not place.address.strip():
        updates["address"] = kakao_address(item)
    if not place.telephone:
        updates["telephone"] = str(item.get("phone") or "").strip() or None
    if place.category == PlaceCategory.OTHER and category != PlaceCategory.OTHER:
        updates["category"] = category
    return place.model_copy(update=updates)


async def enrich_place_with_kakao(
    place: Place,
    *,
    client: httpx.AsyncClient | None = None,
    searcher: Callable[..., Awaitable[list[dict[str, Any]]]] = (
        search_places_by_keyword
    ),
) -> Place:
    """부족한 기본 정보만 보충한다. 실패해도 원본 Place는 유지한다."""
    if not needs_kakao_enrichment(place):
        return place

    try:
        candidates = await searcher(
            place.name,
            longitude=place.longitude,
            latitude=place.latitude,
            client=client,
        )
    except AppException as exc:
        logger.info("카카오 장소 보충을 건너뜁니다: code=%s", exc.code)
        return place

    for candidate in candidates:
        if _is_matching_candidate(place, candidate):
            return _merge_kakao_fields(place, candidate)
    return place

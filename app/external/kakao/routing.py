from __future__ import annotations

import asyncio
from math import ceil
from time import monotonic
from typing import Any

import httpx

from app.algorithms.travel_time import ProviderTravelTime
from app.core.config import get_settings
from app.models.itinerary import TravelMode, TravelTimeSource


KAKAO_PUBLIC_TRANSIT_URL = (
    "https://dapi.kakao.com/v2/routing/publictraffic"
)
KAKAO_WALK_URL = "https://dapi.kakao.com/v2/routing/walk"
KAKAO_ROUTE_CACHE_TTL_SECONDS = 1800
_route_cache: dict[
    tuple[float, float, float, float],
    tuple[float, ProviderTravelTime],
] = {}


def parse_route_minutes(data: Any, *, mode: TravelMode) -> ProviderTravelTime:
    """카카오 경로 응답에서 가장 짧은 실제 소요시간을 추출한다."""
    if not isinstance(data, dict):
        raise ValueError("Kakao Routing 응답 형식이 올바르지 않습니다.")

    response_status = str(data.get("status", "")).strip()
    if response_status != "OK":
        raise ValueError(
            "Kakao Routing 경로 조회 실패: "
            f"status={response_status or 'UNKNOWN'}"
        )

    route_items: list[Any]
    if mode == TravelMode.WALK:
        route = data.get("route")
        route_items = [route] if isinstance(route, dict) else []
    else:
        routes = data.get("routes")
        route_items = routes if isinstance(routes, list) else []
    if not route_items:
        raise ValueError("Kakao Routing 응답에 경로가 없습니다.")

    seconds = [
        route.get("properties", {}).get("totalTime")
        for route in route_items
        if isinstance(route, dict)
        and isinstance(route.get("properties"), dict)
    ]
    valid = [
        value
        for value in seconds
        if isinstance(value, (int, float)) and value > 0
    ]
    if not valid:
        raise ValueError("Kakao Routing 응답에 경로 시간이 없습니다.")

    return ProviderTravelTime(
        minutes=max(1, ceil(min(valid) / 60)),
        mode=mode,
        source=TravelTimeSource.KAKAO,
    )


async def _fetch_route(
    client: httpx.AsyncClient,
    *,
    url: str,
    mode: TravelMode,
    headers: dict[str, str],
    params: dict[str, float],
) -> ProviderTravelTime:
    response = await client.get(url, headers=headers, params=params)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        error_type = ""
        try:
            data = response.json()
            if isinstance(data, dict):
                error_type = str(data.get("errorType") or "").strip()
        except ValueError:
            pass
        raise RuntimeError(
            "Kakao Routing HTTP 오류: "
            f"status={response.status_code} errorType={error_type or 'UNKNOWN'}"
        ) from exc

    try:
        data: Any = response.json()
    except ValueError as exc:
        raise ValueError("Kakao Routing이 JSON이 아닌 응답을 반환했습니다.") from exc
    return parse_route_minutes(data, mode=mode)


async def get_fastest_route(
    origin_longitude: float,
    origin_latitude: float,
    destination_longitude: float,
    destination_latitude: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> ProviderTravelTime:
    """카카오 대중교통과 도보 중 실제 소요시간이 짧은 경로를 반환한다."""
    api_key = get_settings().kakao_rest_api_key.strip()
    if not api_key:
        raise RuntimeError("Kakao REST API 키가 설정되지 않았습니다.")

    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=8.0)
    headers = {"Authorization": f"KakaoAK {api_key}"}
    params = {
        "start_x": origin_longitude,
        "start_y": origin_latitude,
        "end_x": destination_longitude,
        "end_y": destination_latitude,
    }
    try:
        results = await asyncio.gather(
            _fetch_route(
                active_client,
                url=KAKAO_PUBLIC_TRANSIT_URL,
                mode=TravelMode.TRANSIT,
                headers=headers,
                params=params,
            ),
            _fetch_route(
                active_client,
                url=KAKAO_WALK_URL,
                mode=TravelMode.WALK,
                headers=headers,
                params=params,
            ),
            return_exceptions=True,
        )
    finally:
        if owns_client:
            await active_client.aclose()

    valid = [
        result for result in results if isinstance(result, ProviderTravelTime)
    ]
    if not valid:
        reasons = ",".join(type(result).__name__ for result in results)
        raise RuntimeError(
            "Kakao 대중교통·도보 경로를 모두 조회하지 못했습니다: "
            f"reasons={reasons}"
        )
    return min(valid, key=lambda result: result.minutes)


async def get_cached_fastest_route(
    origin_longitude: float,
    origin_latitude: float,
    destination_longitude: float,
    destination_latitude: float,
) -> ProviderTravelTime:
    key = tuple(
        round(value, 5)
        for value in (
            origin_longitude,
            origin_latitude,
            destination_longitude,
            destination_latitude,
        )
    )
    now = monotonic()
    cached = _route_cache.get(key)
    if cached is not None and cached[0] > now:
        return cached[1]

    result = await get_fastest_route(
        origin_longitude,
        origin_latitude,
        destination_longitude,
        destination_latitude,
    )
    _route_cache[key] = (now + KAKAO_ROUTE_CACHE_TTL_SECONDS, result)
    return result

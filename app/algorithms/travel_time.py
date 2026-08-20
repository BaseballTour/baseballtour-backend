from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from typing import Awaitable, Callable, Protocol

from app.models.itinerary import TripInput
from app.models.itinerary import TravelMode, TravelTimeSource
from app.models.place import Place


logger = logging.getLogger(__name__)


class Coordinate(Protocol):
    latitude: float
    longitude: float


TRAVEL_TIME_MAX_CONCURRENCY = 8
TRAVEL_TIME_PROVIDER_TIMEOUT_SECONDS = 8.0
TRAVEL_TIME_MATRIX_TIMEOUT_SECONDS = 30.0
ANCHOR_NODE_IDS = {
    "arrival",
    "departure",
    "stadium",
    "accommodation",
}
PLACE_NEAREST_NEIGHBOR_COUNT = 2


def _safe_provider_error(exc: Exception) -> str:
    """요청 URL과 API 키가 로그에 포함되지 않도록 오류를 축약한다."""
    if isinstance(exc, (RuntimeError, ValueError)):
        return f"{type(exc).__name__}: {exc}"
    return type(exc).__name__


@dataclass(frozen=True)
class MatrixNode:
    node_id: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class ProviderTravelTime:
    minutes: int
    mode: TravelMode
    source: TravelTimeSource


TravelTimeProvider = Callable[
    [float, float, float, float],
    Awaitable[int | ProviderTravelTime],
]


@dataclass
class TravelTimeMatrix:
    minutes: dict[tuple[str, str], int]
    modes: dict[tuple[str, str], TravelMode] | None = None
    sources: dict[tuple[str, str], TravelTimeSource] | None = None

    def get(self, origin_id: str, destination_id: str) -> int:
        if origin_id == destination_id:
            return 0
        return self.minutes[(origin_id, destination_id)]

    def get_mode(
        self,
        origin_id: str,
        destination_id: str,
    ) -> TravelMode | None:
        if origin_id == destination_id:
            return None
        if self.modes is None:
            return TravelMode.TRANSIT
        return self.modes.get((origin_id, destination_id))

    def get_source(
        self,
        origin_id: str,
        destination_id: str,
    ) -> TravelTimeSource | None:
        if origin_id == destination_id:
            return None
        if self.sources is None:
            return TravelTimeSource.FAKE
        return self.sources.get((origin_id, destination_id))


def haversine_kilometers(origin: Coordinate, destination: Coordinate) -> float:
    latitude_delta = radians(
        destination.latitude - origin.latitude
    )
    longitude_delta = radians(
        destination.longitude - origin.longitude
    )
    origin_latitude = radians(origin.latitude)
    destination_latitude = radians(destination.latitude)
    value = (
        sin(latitude_delta / 2) ** 2
        + cos(origin_latitude)
        * cos(destination_latitude)
        * sin(longitude_delta / 2) ** 2
    )
    return 6371.0 * 2 * asin(sqrt(value))


def estimated_walking_minutes(
    origin: Coordinate,
    destination: Coordinate,
) -> int:
    """직선거리에 우회계수를 적용해 도보시간을 추정한다."""
    distance = haversine_kilometers(origin, destination)
    adjusted_distance = distance * 1.25
    return max(1, round(adjusted_distance / 4.5 * 60))


def fallback_travel_minutes(origin: Coordinate, destination: Coordinate) -> int:
    """호환성을 위한 도보 예상시간 alias."""
    return estimated_walking_minutes(origin, destination)


async def build_travel_time_matrix(
    nodes: list[MatrixNode],
    provider: TravelTimeProvider | None = None,
    *,
    max_concurrency: int = TRAVEL_TIME_MAX_CONCURRENCY,
    provider_timeout_seconds: float = (
        TRAVEL_TIME_PROVIDER_TIMEOUT_SECONDS
    ),
    matrix_timeout_seconds: float = TRAVEL_TIME_MATRIX_TIMEOUT_SECONDS,
    provider_route_keys: set[tuple[str, str]] | None = None,
) -> TravelTimeMatrix:
    unique = {node.node_id: node for node in nodes}
    minutes: dict[tuple[str, str], int] = {}
    modes: dict[tuple[str, str], TravelMode] = {}
    sources: dict[tuple[str, str], TravelTimeSource] = {}

    routes: list[tuple[str, MatrixNode, str, MatrixNode]] = []

    for origin_id, origin in unique.items():
        for destination_id, destination in unique.items():
            if origin_id == destination_id:
                continue
            key = (origin_id, destination_id)
            if key in minutes:
                continue
            walk_minutes = estimated_walking_minutes(origin, destination)
            minutes[key] = walk_minutes
            modes[key] = TravelMode.WALK
            sources[key] = TravelTimeSource.ESTIMATED
            if provider_route_keys is None or key in provider_route_keys:
                routes.append(
                    (origin_id, origin, destination_id, destination)
                )

    if provider is not None and routes:
        # 전체 시간 예산이 끝나더라도 일정의 뼈대를 구성하는 Anchor 경로가
        # 먼저 실제 대중교통 시간으로 보정되도록 처리 순서를 정한다.
        routes.sort(
            key=lambda route: (
                0
                if route[0] in ANCHOR_NODE_IDS
                and route[2] in ANCHOR_NODE_IDS
                else 1
                if route[0] in ANCHOR_NODE_IDS
                or route[2] in ANCHOR_NODE_IDS
                else 2,
            )
        )
        semaphore = asyncio.Semaphore(max_concurrency)
        failures: list[tuple[str, str, str]] = []

        async def resolve_route(
            origin_id: str,
            origin: MatrixNode,
            destination_id: str,
            destination: MatrixNode,
        ) -> None:
            try:
                async with semaphore:
                    provider_result = await asyncio.wait_for(
                        provider(
                            origin.longitude,
                            origin.latitude,
                            destination.longitude,
                            destination.latitude,
                        ),
                        timeout=provider_timeout_seconds,
                    )
            except Exception as exc:
                failures.append(
                    (
                        origin_id,
                        destination_id,
                        _safe_provider_error(exc),
                    )
                )
                return

            key = (origin_id, destination_id)
            if isinstance(provider_result, ProviderTravelTime):
                minutes[key] = provider_result.minutes
                modes[key] = provider_result.mode
                sources[key] = provider_result.source
            elif provider_result < minutes[key]:
                # 기존 int Provider(ODsay 및 테스트 double)와의 호환성.
                minutes[key] = provider_result
                modes[key] = TravelMode.TRANSIT
                sources[key] = TravelTimeSource.ODSAY

        tasks = [
            resolve_route(*route)
            for route in routes
        ]
        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks),
                timeout=matrix_timeout_seconds,
            )
        except asyncio.TimeoutError:
            # 완료되지 않은 경로는 미리 채운 직선거리 기반 값으로 유지합니다.
            logger.warning(
                "외부 이동시간 Matrix 전체 제한시간 초과: "
                "timeout_seconds=%s total_routes=%s",
                matrix_timeout_seconds,
                len(routes),
            )

        if failures:
            # 키나 요청 URL은 남기지 않고 대표 실패만 기록한다.
            sample = failures[0]
            logger.warning(
                "외부 경로 조회 실패로 예상시간 사용: "
                "failed_routes=%s total_routes=%s "
                "sample_origin=%s sample_destination=%s reason=%s",
                len(failures),
                len(routes),
                sample[0],
                sample[1],
                sample[2],
            )

    return TravelTimeMatrix(
        minutes=minutes,
        modes=modes,
        sources=sources,
    )


async def build_itinerary_travel_time_matrix(
    trip: TripInput,
    places: list[Place],
    provider: TravelTimeProvider | None = None,
) -> TravelTimeMatrix:
    nodes = [
        MatrixNode(
            "arrival",
            trip.arrival_point.latitude,
            trip.arrival_point.longitude,
        ),
        MatrixNode(
            "departure",
            trip.departure_point.latitude,
            trip.departure_point.longitude,
        ),
        MatrixNode(
            "stadium",
            trip.game_anchor.latitude,
            trip.game_anchor.longitude,
        ),
    ]
    if trip.accommodation is not None:
        nodes.append(
            MatrixNode(
                "accommodation",
                trip.accommodation.latitude,
                trip.accommodation.longitude,
            )
        )
    nodes.extend(
        MatrixNode(
            place.place_id,
            place.latitude,
            place.longitude,
        )
        for place in places
    )
    provider_route_keys = _itinerary_provider_route_keys(nodes)
    return await build_travel_time_matrix(
        nodes,
        provider,
        provider_route_keys=provider_route_keys,
    )


def _itinerary_provider_route_keys(
    nodes: list[MatrixNode],
) -> set[tuple[str, str]]:
    """일정 계산에 유용한 경로만 외부 API로 조회한다."""
    anchors = [node for node in nodes if node.node_id in ANCHOR_NODE_IDS]
    places = [node for node in nodes if node.node_id not in ANCHOR_NODE_IDS]
    keys = {
        (origin.node_id, destination.node_id)
        for origin in anchors
        for destination in anchors
        if origin.node_id != destination.node_id
    }

    start_anchor_ids = {"arrival"}
    if any(node.node_id == "accommodation" for node in anchors):
        start_anchor_ids.add("accommodation")
    end_anchor_ids = {"stadium", "departure"}
    if any(node.node_id == "accommodation" for node in anchors):
        end_anchor_ids.add("accommodation")

    for place in places:
        keys.update(
            (anchor_id, place.node_id)
            for anchor_id in start_anchor_ids
        )
        keys.update(
            (place.node_id, anchor_id)
            for anchor_id in end_anchor_ids
        )

        neighbors = sorted(
            (
                candidate
                for candidate in places
                if candidate.node_id != place.node_id
            ),
            key=lambda candidate: haversine_kilometers(place, candidate),
        )[:PLACE_NEAREST_NEIGHBOR_COUNT]
        keys.update(
            (place.node_id, neighbor.node_id)
            for neighbor in neighbors
        )

    return keys

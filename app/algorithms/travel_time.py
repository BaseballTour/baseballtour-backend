from __future__ import annotations

import asyncio
from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from typing import Awaitable, Callable, Protocol

from app.models.itinerary import TripInput
from app.models.itinerary import TravelMode, TravelTimeSource
from app.models.place import Place


class Coordinate(Protocol):
    latitude: float
    longitude: float


TravelTimeProvider = Callable[
    [float, float, float, float],
    Awaitable[int],
]

TRAVEL_TIME_MAX_CONCURRENCY = 8
TRAVEL_TIME_PROVIDER_TIMEOUT_SECONDS = 3.0
TRAVEL_TIME_MATRIX_TIMEOUT_SECONDS = 20.0


@dataclass(frozen=True)
class MatrixNode:
    node_id: str
    latitude: float
    longitude: float


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
            routes.append(
                (origin_id, origin, destination_id, destination)
            )

    if provider is not None and routes:
        semaphore = asyncio.Semaphore(max_concurrency)

        async def resolve_route(
            origin_id: str,
            origin: MatrixNode,
            destination_id: str,
            destination: MatrixNode,
        ) -> None:
            try:
                async with semaphore:
                    transit_minutes = await asyncio.wait_for(
                        provider(
                            origin.longitude,
                            origin.latitude,
                            destination.longitude,
                            destination.latitude,
                        ),
                        timeout=provider_timeout_seconds,
                    )
            except Exception:
                return

            key = (origin_id, destination_id)
            if transit_minutes < minutes[key]:
                minutes[key] = transit_minutes
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
            pass

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
    return await build_travel_time_matrix(nodes, provider)

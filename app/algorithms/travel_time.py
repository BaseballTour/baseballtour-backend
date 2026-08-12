from __future__ import annotations

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
) -> TravelTimeMatrix:
    unique = {node.node_id: node for node in nodes}
    minutes: dict[tuple[str, str], int] = {}
    modes: dict[tuple[str, str], TravelMode] = {}
    sources: dict[tuple[str, str], TravelTimeSource] = {}

    for origin_id, origin in unique.items():
        for destination_id, destination in unique.items():
            if origin_id == destination_id:
                continue
            key = (origin_id, destination_id)
            if key in minutes:
                continue
            walk_minutes = estimated_walking_minutes(origin, destination)
            value = walk_minutes
            mode = TravelMode.WALK
            source = TravelTimeSource.ESTIMATED
            if provider is not None:
                try:
                    transit_minutes = await provider(
                        origin.longitude,
                        origin.latitude,
                        destination.longitude,
                        destination.latitude,
                    )
                    if transit_minutes < walk_minutes:
                        value = transit_minutes
                        mode = TravelMode.TRANSIT
                        source = TravelTimeSource.ODSAY
                except Exception:
                    pass
            minutes[key] = value
            modes[key] = mode
            sources[key] = source

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

from __future__ import annotations

from dataclasses import dataclass, field
from math import asin, cos, radians, sin, sqrt
from typing import Awaitable, Callable, Protocol

from app.models.itinerary import TripInput, TravelTimeSource
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
    sources: dict[
        tuple[str, str],
        TravelTimeSource,
    ] = field(default_factory=dict)

    def get(self, origin_id: str, destination_id: str) -> int:
        if origin_id == destination_id:
            return 0
        return self.minutes[(origin_id, destination_id)]

    def get_source(
        self,
        origin_id: str,
        destination_id: str,
    ) -> TravelTimeSource | None:
        if origin_id == destination_id:
            return None

        return self.sources.get(
            (origin_id, destination_id),
            TravelTimeSource.FAKE,
        )


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


def fallback_travel_minutes(origin: Coordinate, destination: Coordinate) -> int:
    """대중교통 실패 시 직선거리와 평균속도로 보수적으로 추정한다."""
    distance = haversine_kilometers(origin, destination)
    return max(5, round(distance / 20 * 60 + 10))


async def build_travel_time_matrix(
    nodes: list[MatrixNode],
    provider: TravelTimeProvider | None = None,
) -> TravelTimeMatrix:
    unique = {node.node_id: node for node in nodes}
    minutes: dict[tuple[str, str], int] = {}
    sources: dict[tuple[str, str], TravelTimeSource] = {}

    for origin_id, origin in unique.items():
        for destination_id, destination in unique.items():
            if origin_id == destination_id:
                continue

            key = (origin_id, destination_id)
            if key in minutes:
                continue

            value: int | None = None

            if provider is not None:
                try:
                    value = await provider(
                        origin.longitude,
                        origin.latitude,
                        destination.longitude,
                        destination.latitude,
                    )
                except Exception:
                    value = None

            if value is not None:
                minutes[key] = value
                sources[key] = TravelTimeSource.ODSAY
            else:
                minutes[key] = fallback_travel_minutes(
                    origin,
                    destination,
                )
                sources[key] = TravelTimeSource.ESTIMATED

    return TravelTimeMatrix(
        minutes=minutes,
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

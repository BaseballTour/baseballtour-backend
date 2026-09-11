import asyncio
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.algorithms.travel_time import (
    MatrixNode,
    ProviderTravelTime,
    _itinerary_provider_route_keys,
    build_travel_time_matrix,
    estimated_walking_minutes,
    fallback_travel_minutes,
    scheduled_itinerary_provider_route_keys,
)
from app.models.itinerary import ItineraryResult, TravelMode, TravelTimeSource


def test_fallback_travel_time_is_positive() -> None:
    origin = MatrixNode("origin", 37.5122, 127.0719)
    destination = MatrixNode("destination", 37.4982, 126.8671)

    assert fallback_travel_minutes(origin, destination) >= 5


def test_estimated_walking_time_is_positive() -> None:
    origin = MatrixNode("origin", 37.5122, 127.0719)
    destination = MatrixNode("destination", 37.5101, 127.0767)

    assert estimated_walking_minutes(origin, destination) >= 1


@pytest.mark.anyio
async def test_matrix_uses_provider_and_deduplicates_nodes() -> None:
    calls = 0

    async def provider(*coordinates: float) -> int:
        nonlocal calls
        calls += 1
        return 1

    matrix = await build_travel_time_matrix(
        [
            MatrixNode("a", 37.5, 127.0),
            MatrixNode("a", 37.5, 127.0),
            MatrixNode("b", 37.6, 127.1),
        ],
        provider,
    )

    assert matrix.get("a", "b") == 1
    assert matrix.get("b", "a") == 1
    assert matrix.get_mode("a", "b").value == "TRANSIT"
    assert matrix.get_source("a", "b").value == "ESTIMATED"
    assert calls == 2


@pytest.mark.anyio
async def test_matrix_falls_back_when_provider_fails(caplog) -> None:
    async def failing_provider(*coordinates: float) -> int:
        raise RuntimeError("provider unavailable")

    matrix = await build_travel_time_matrix(
        [
            MatrixNode("a", 37.5, 127.0),
            MatrixNode("b", 37.6, 127.1),
        ],
        failing_provider,
    )

    assert matrix.get("a", "b") >= 5
    assert matrix.get_mode("a", "b").value == "WALK"
    assert matrix.get_source("a", "b").value == "ESTIMATED"
    assert "외부 경로 조회 실패로 예상시간 사용" in caplog.text
    assert "RuntimeError: provider unavailable" in caplog.text


@pytest.mark.anyio
async def test_matrix_prefers_walking_when_faster() -> None:
    async def slow_transit(*coordinates: float) -> int:
        return 30

    matrix = await build_travel_time_matrix(
        [
            MatrixNode("a", 37.5122, 127.0719),
            MatrixNode("b", 37.5101, 127.0767),
        ],
        slow_transit,
    )

    assert matrix.get("a", "b") < 30
    assert matrix.get_mode("a", "b").value == "WALK"
    assert matrix.get_source("a", "b").value == "ESTIMATED"


@pytest.mark.anyio
async def test_matrix_limits_provider_concurrency() -> None:
    active = 0
    maximum_active = 0

    async def provider(*coordinates: float) -> int:
        nonlocal active, maximum_active
        active += 1
        maximum_active = max(maximum_active, active)
        await asyncio.sleep(0.01)
        active -= 1
        return 1

    await build_travel_time_matrix(
        [
            MatrixNode(str(index), 37.5 + index / 100, 127.0)
            for index in range(5)
        ],
        provider,
        max_concurrency=2,
    )

    assert maximum_active == 2


@pytest.mark.anyio
async def test_matrix_uses_fallback_after_total_timeout(caplog) -> None:
    async def slow_provider(*coordinates: float) -> int:
        await asyncio.sleep(1)
        return 1

    matrix = await build_travel_time_matrix(
        [
            MatrixNode("a", 37.5, 127.0),
            MatrixNode("b", 37.6, 127.1),
        ],
        slow_provider,
        provider_timeout_seconds=1,
        matrix_timeout_seconds=0.01,
    )

    assert matrix.get("a", "b") >= 5
    assert matrix.get_source("a", "b").value == "ESTIMATED"
    assert "외부 이동시간 Matrix 전체 제한시간 초과" in caplog.text


@pytest.mark.anyio
async def test_matrix_uses_structured_kakao_result() -> None:
    async def provider(*coordinates: float) -> ProviderTravelTime:
        return ProviderTravelTime(
            minutes=20,
            mode=TravelMode.WALK,
            source=TravelTimeSource.KAKAO,
        )

    matrix = await build_travel_time_matrix(
        [
            MatrixNode("a", 37.5, 127.0),
            MatrixNode("b", 37.5001, 127.0001),
        ],
        provider,
    )

    assert matrix.get("a", "b") == 20
    assert matrix.get_mode("a", "b") == TravelMode.WALK
    assert matrix.get_source("a", "b") == TravelTimeSource.KAKAO


def test_itinerary_provider_routes_are_reduced() -> None:
    nodes = [
        MatrixNode("arrival", 37.5, 127.0),
        MatrixNode("departure", 37.51, 127.01),
        MatrixNode("stadium", 37.52, 127.02),
        *[
            MatrixNode(
                f"tour_{index}",
                37.53 + index / 1000,
                127.03 + index / 1000,
            )
            for index in range(15)
        ],
    ]

    keys = _itinerary_provider_route_keys(nodes)

    assert len(keys) == 81
    assert len(keys) < len(nodes) * (len(nodes) - 1)
    assert ("arrival", "tour_0") in keys
    assert ("tour_0", "stadium") in keys


def test_scheduled_routes_only_include_adjacent_itinerary_items() -> None:
    result = ItineraryResult.model_validate(
        {
            "tripId": "trip_1",
            "algorithmVersion": "test",
            "totalTravelMinutes": 0,
            "days": [
                {
                    "date": "2026-09-11",
                    "dayType": "GAME_DAY",
                    "items": [
                        {
                            "type": "ARRIVAL_POINT",
                            "sequence": 1,
                            "name": "도착지",
                            "address": "서울",
                            "latitude": 37.5,
                            "longitude": 127.0,
                            "scheduledStartAt": datetime.fromisoformat("2026-09-11T10:00:00+09:00"),
                            "scheduledEndAt": datetime.fromisoformat("2026-09-11T10:20:00+09:00"),
                        },
                        {
                            "type": "PLACE",
                            "sequence": 2,
                            "placeId": "tour_1",
                            "name": "장소",
                            "address": "서울",
                            "latitude": 37.51,
                            "longitude": 127.01,
                            "scheduledStartAt": datetime.fromisoformat("2026-09-11T11:00:00+09:00"),
                            "scheduledEndAt": datetime.fromisoformat("2026-09-11T12:00:00+09:00"),
                        },
                        {
                            "type": "STADIUM",
                            "sequence": 3,
                            "name": "경기장",
                            "address": "서울",
                            "latitude": 37.52,
                            "longitude": 127.02,
                            "scheduledStartAt": datetime.fromisoformat("2026-09-11T17:20:00+09:00"),
                            "scheduledEndAt": datetime.fromisoformat("2026-09-11T21:00:00+09:00"),
                        },
                    ],
                }
            ],
        }
    )

    keys = scheduled_itinerary_provider_route_keys(
        result, has_accommodation=False
    )

    assert keys == {("arrival", "tour_1"), ("tour_1", "stadium")}


@pytest.mark.anyio
async def test_existing_matrix_only_fetches_new_routes() -> None:
    first_nodes = [
        MatrixNode("arrival", 37.5, 127.0),
        MatrixNode("stadium", 37.51, 127.01),
    ]
    provider = AsyncMock(return_value=7)
    initial = await build_travel_time_matrix(first_nodes, provider)
    initial_call_count = provider.await_count

    extended = await build_travel_time_matrix(
        [*first_nodes, MatrixNode("tour_new", 37.52, 127.02)],
        provider,
        existing_matrix=initial,
    )

    assert provider.await_count - initial_call_count == 4
    assert extended.get("arrival", "stadium") == initial.get(
        "arrival", "stadium"
    )
    assert extended.get("arrival", "tour_new") == 7

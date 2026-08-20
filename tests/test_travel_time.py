import asyncio

import pytest

from app.algorithms.travel_time import (
    MatrixNode,
    ProviderTravelTime,
    _itinerary_provider_route_keys,
    build_travel_time_matrix,
    estimated_walking_minutes,
    fallback_travel_minutes,
)
from app.models.itinerary import TravelMode, TravelTimeSource


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
    assert matrix.get_source("a", "b").value == "ODSAY"
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

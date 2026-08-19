import pytest

from app.algorithms.travel_time import (
    MatrixNode,
    build_travel_time_matrix,
    estimated_walking_minutes,
    fallback_travel_minutes,
)


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
async def test_matrix_falls_back_when_provider_fails() -> None:
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

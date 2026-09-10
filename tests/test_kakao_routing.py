from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.algorithms.travel_time import ProviderTravelTime
from app.external.kakao import routing
from app.models.itinerary import TravelMode, TravelTimeSource


def test_parses_fastest_public_transit_route() -> None:
    result = routing.parse_route_minutes(
        {
            "status": "OK",
            "routes": [
                {"properties": {"totalTime": 2115}},
                {"properties": {"totalTime": 1801}},
            ],
        },
        mode=TravelMode.TRANSIT,
    )

    assert result.minutes == 31
    assert result.mode == TravelMode.TRANSIT
    assert result.source == TravelTimeSource.KAKAO


def test_parses_walk_route() -> None:
    result = routing.parse_route_minutes(
        {
            "status": "OK",
            "route": {"properties": {"totalTime": 601}},
        },
        mode=TravelMode.WALK,
    )

    assert result.minutes == 11
    assert result.mode == TravelMode.WALK


def test_rejects_route_error_status() -> None:
    with pytest.raises(ValueError, match="status=NO_RESULTS"):
        routing.parse_route_minutes(
            {"status": "NO_RESULTS"},
            mode=TravelMode.TRANSIT,
        )


@pytest.mark.anyio
async def test_fastest_route_compares_transit_and_walk(monkeypatch) -> None:
    monkeypatch.setattr(
        routing,
        "get_settings",
        lambda: SimpleNamespace(kakao_rest_api_key="test-key"),
    )
    monkeypatch.setattr(
        routing,
        "_fetch_route",
        AsyncMock(
            side_effect=[
                ProviderTravelTime(
                    25,
                    TravelMode.TRANSIT,
                    TravelTimeSource.KAKAO,
                ),
                ProviderTravelTime(
                    12,
                    TravelMode.WALK,
                    TravelTimeSource.KAKAO,
                ),
            ]
        ),
    )

    result = await routing.get_fastest_route(
        127.0,
        37.5,
        127.1,
        37.6,
        client=AsyncMock(),
    )

    assert result.minutes == 12
    assert result.mode == TravelMode.WALK


@pytest.mark.anyio
async def test_route_cache_avoids_duplicate_pair(monkeypatch) -> None:
    routing._route_cache.clear()
    getter = AsyncMock(
        return_value=ProviderTravelTime(
            20,
            TravelMode.TRANSIT,
            TravelTimeSource.KAKAO,
        )
    )
    monkeypatch.setattr(routing, "get_fastest_route", getter)

    first = await routing.get_cached_fastest_route(127.0, 37.5, 127.1, 37.6)
    second = await routing.get_cached_fastest_route(127.0, 37.5, 127.1, 37.6)

    assert first == second
    getter.assert_awaited_once()


@pytest.mark.anyio
async def test_route_cache_avoids_repeating_recent_failure(monkeypatch) -> None:
    routing._route_cache.clear()
    getter = AsyncMock(side_effect=RuntimeError("route unavailable"))
    monkeypatch.setattr(routing, "get_fastest_route", getter)

    for _ in range(2):
        with pytest.raises(RuntimeError, match="route unavailable"):
            await routing.get_cached_fastest_route(
                127.0,
                37.5,
                127.1,
                37.6,
            )

    getter.assert_awaited_once()


def test_route_cache_prunes_expired_and_oldest_entries(monkeypatch) -> None:
    routing._route_cache.clear()
    monkeypatch.setattr(routing, "KAKAO_ROUTE_CACHE_MAX_ENTRIES", 2)
    routing._route_cache[(1.0, 1.0, 1.0, 1.0)] = (
        0.0,
        RuntimeError("expired"),
    )
    valid = ProviderTravelTime(
        10,
        TravelMode.WALK,
        TravelTimeSource.KAKAO,
    )
    routing._route_cache[(2.0, 2.0, 2.0, 2.0)] = (9_999_999_999.0, valid)
    routing._route_cache[(3.0, 3.0, 3.0, 3.0)] = (9_999_999_999.0, valid)
    routing._route_cache[(4.0, 4.0, 4.0, 4.0)] = (9_999_999_999.0, valid)

    routing._prune_route_cache(1.0)

    assert len(routing._route_cache) == 2
    assert (1.0, 1.0, 1.0, 1.0) not in routing._route_cache
    assert (2.0, 2.0, 2.0, 2.0) not in routing._route_cache

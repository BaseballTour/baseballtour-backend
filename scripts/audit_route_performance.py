import asyncio
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from time import perf_counter

from app.algorithms.travel_time import build_itinerary_travel_time_matrix
from app.external.kakao import routing
from app.models.itinerary import GameAnchor, GeoPoint, TripInput
from app.models.place import Place, PlaceCategory, PlaceSource


async def main() -> None:
    quality_path = Path("artifacts/recommendation-quality.json")
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    region = quality[0]
    candidates = [
        Place(
            place_id=item["placeId"],
            name=item["name"],
            category=PlaceCategory(item["category"]),
            latitude=item["latitude"],
            longitude=item["longitude"],
            source=PlaceSource.TOUR_API,
            source_content_id=item["placeId"].removeprefix("tour_"),
        )
        for item in region["candidates"][:2]
    ]
    latitude, longitude = 37.5122, 127.0719
    trip = TripInput(
        trip_id="route_audit",
        trip_start_at=datetime.fromisoformat("2026-08-15T10:00:00+09:00"),
        trip_end_at=datetime.fromisoformat("2026-08-17T22:00:00+09:00"),
        arrival_point=GeoPoint(
            name="잠실 도착지",
            address="잠실",
            latitude=latitude,
            longitude=longitude,
        ),
        departure_point=GeoPoint(
            name="잠실 출발지",
            address="잠실",
            latitude=latitude,
            longitude=longitude,
        ),
        game_anchor=GameAnchor(
            game_id="route_audit_game",
            stadium_id="jamsil",
            name="잠실야구장",
            address="서울특별시 송파구 올림픽로 25",
            latitude=latitude,
            longitude=longitude,
            game_start_at=datetime.fromisoformat(
                "2026-08-16T18:30:00+09:00"
            ),
        ),
    )

    routing._route_cache.clear()
    original_fetch = routing._fetch_route
    http_calls = 0

    async def counted_fetch(*args, **kwargs):
        nonlocal http_calls
        http_calls += 1
        return await original_fetch(*args, **kwargs)

    routing._fetch_route = counted_fetch
    started = perf_counter()
    cold = await build_itinerary_travel_time_matrix(
        trip,
        candidates,
        routing.get_cached_fastest_route,
    )
    cold_seconds = perf_counter() - started
    cold_calls = http_calls

    started = perf_counter()
    warm = await build_itinerary_travel_time_matrix(
        trip,
        candidates,
        routing.get_cached_fastest_route,
    )
    warm_seconds = perf_counter() - started
    warm_calls = http_calls - cold_calls

    result = {
        "candidateCount": len(candidates),
        "coldElapsedSeconds": round(cold_seconds, 3),
        "warmElapsedSeconds": round(warm_seconds, 3),
        "coldKakaoHttpCalls": cold_calls,
        "warmKakaoHttpCalls": warm_calls,
        "coldSourceDistribution": dict(
            Counter(str(value) for value in cold.sources.values())
        ),
        "warmSourceDistribution": dict(
            Counter(str(value) for value in warm.sources.values())
        ),
        "coldModeDistribution": dict(
            Counter(str(value) for value in cold.modes.values())
        ),
    }
    output = Path("artifacts/route-performance.json")
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(output.resolve())


if __name__ == "__main__":
    asyncio.run(main())

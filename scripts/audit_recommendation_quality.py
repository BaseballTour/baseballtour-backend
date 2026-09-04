import argparse
import asyncio
import json
from collections import Counter
from datetime import date, datetime, time, timedelta
from pathlib import Path
from time import perf_counter
from zoneinfo import ZoneInfo

from app.external.tour_api import adapter as adapter_module
from app.external.tour_api.adapter import TourApiAdapter
from app.external.kakao.routing import get_cached_fastest_route
from app.algorithms.itinerary_generator import generate_itinerary
from app.algorithms.travel_time import build_itinerary_travel_time_matrix
from app.models.itinerary import GameAnchor, GeoPoint, TripInput
from app.services.recommendation import (
    ExcludedRecommendationPlace,
    RecommendationCenter,
    RecommendationService,
)
from app.services.itinerary_generation_service import ItineraryGenerationService


STADIUMS = {
    "잠실": ("잠실야구장", 37.5122, 127.0719),
    "고척": ("고척스카이돔", 37.4982, 126.8671),
    "사직": ("사직야구장", 35.1940, 129.0615),
    "대전": ("대전 한화생명 볼파크", 36.3172, 127.4292),
    "인천": ("인천 SSG 랜더스필드", 37.4370, 126.6932),
}
KOREA_TIMEZONE = ZoneInfo("Asia/Seoul")


def _distribution(places) -> dict[str, int]:
    return dict(
        sorted(Counter(str(place.category) for place in places).items())
    )


def _install_call_counters() -> Counter[str]:
    calls: Counter[str] = Counter()
    function_names = (
        "get_nearby_places",
        "get_place_common_info",
        "get_place_intro_info",
        "get_place_images",
    )
    for name in function_names:
        original = getattr(adapter_module, name)

        async def counted(*args, _name=name, _original=original, **kwargs):
            calls[_name] += 1
            return await _original(*args, **kwargs)

        setattr(adapter_module, name, counted)
    return calls


async def _inspect_region(
    label: str,
    stadium,
    calls: Counter[str],
    *,
    live_routes: bool = False,
    max_candidates: int = 20,
    travel_start_date: date = date(2026, 8, 15),
    nights: int = 2,
) -> dict:
    name, latitude, longitude = stadium
    adapter = TourApiAdapter(cache_ttl_seconds=300)
    service = RecommendationService(adapter, max_candidates=max_candidates)
    diagnostics: dict[str, object] = {}
    before = calls.copy()
    started = perf_counter()
    candidates = await service.get_candidates(
        centers=[RecommendationCenter(latitude=latitude, longitude=longitude)],
        excluded_places=[
            ExcludedRecommendationPlace(
                name=name,
                latitude=latitude,
                longitude=longitude,
            )
        ],
        travel_start_date=travel_start_date,
        travel_end_date=travel_start_date + timedelta(days=nights),
        diagnostics=diagnostics,
    )
    cold_seconds = perf_counter() - started
    cold_calls = calls - before

    before_warm = calls.copy()
    warm_started = perf_counter()
    warm_candidates = await service.get_candidates(
        centers=[RecommendationCenter(latitude=latitude, longitude=longitude)],
        excluded_places=[
            ExcludedRecommendationPlace(
                name=name,
                latitude=latitude,
                longitude=longitude,
            )
        ],
        travel_start_date=travel_start_date,
        travel_end_date=travel_start_date + timedelta(days=nights),
    )
    warm_seconds = perf_counter() - warm_started
    warm_calls = calls - before_warm

    trip = TripInput(
        trip_id=f"audit_{label}",
        trip_start_at=datetime.combine(
            travel_start_date,
            time(10, 0),
            tzinfo=KOREA_TIMEZONE,
        ),
        trip_end_at=datetime.combine(
            travel_start_date + timedelta(days=nights),
            time(22, 0),
            tzinfo=KOREA_TIMEZONE,
        ),
        arrival_point=GeoPoint(
            name=f"{label} 도착지",
            address=f"{label} 도착지",
            latitude=latitude,
            longitude=longitude,
        ),
        departure_point=GeoPoint(
            name=f"{label} 출발지",
            address=f"{label} 출발지",
            latitude=latitude,
            longitude=longitude,
        ),
        game_anchor=GameAnchor(
            game_id=f"audit_game_{label}",
            stadium_id=label,
            name=name,
            address=name,
            latitude=latitude,
            longitude=longitude,
            game_start_at=datetime.combine(
                travel_start_date + timedelta(days=1),
                time(18, 30),
                tzinfo=KOREA_TIMEZONE,
            ),
        ),
    )
    matrix_started = perf_counter()
    matrix = await build_itinerary_travel_time_matrix(
        trip,
        candidates,
        provider=get_cached_fastest_route if live_routes else None,
    )
    itinerary = generate_itinerary(
        trip,
        [],
        matrix,
        recommended_places=candidates,
        recommendation_diagnostics=diagnostics,
    )
    supplement_dates = (
        ItineraryGenerationService._recommendation_supplement_dates(itinerary)
    )
    supplemental_candidates = []
    if supplement_dates:
        supplemental_candidates = await service.get_candidates(
            centers=(
                ItineraryGenerationService._supplement_recommendation_centers(
                    result=itinerary,
                    target_dates=supplement_dates,
                )
            ),
            selected_place_ids={place.place_id for place in candidates},
            excluded_places=[
                ExcludedRecommendationPlace(
                    name=name,
                    latitude=latitude,
                    longitude=longitude,
                )
            ],
            travel_start_date=min(supplement_dates),
            travel_end_date=max(supplement_dates),
        )
        if supplemental_candidates:
            matrix = await build_itinerary_travel_time_matrix(
                trip,
                [*candidates, *supplemental_candidates],
                provider=get_cached_fastest_route if live_routes else None,
            )
            itinerary = generate_itinerary(
                trip,
                [],
                matrix,
                recommended_places=candidates,
                supplemental_recommendations_by_date={
                    target_date: supplemental_candidates
                    for target_date in supplement_dates
                },
                recommendation_diagnostics=diagnostics,
            )
    schedule_seconds = perf_counter() - matrix_started

    return {
        "region": label,
        "routeProvider": "KAKAO" if live_routes else "ESTIMATED",
        "stadium": name,
        "coldElapsedSeconds": round(cold_seconds, 3),
        "warmElapsedSeconds": round(warm_seconds, 3),
        "coldExternalCalls": dict(cold_calls),
        "warmExternalCalls": dict(warm_calls),
        "scheduleElapsedSeconds": round(schedule_seconds, 3),
        "routeSourceDistribution": dict(
            sorted(
                Counter(
                    source.value
                    for source in (matrix.sources or {}).values()
                ).items()
            )
        ),
        "routeModeDistribution": dict(
            sorted(
                Counter(
                    mode.value
                    for mode in (matrix.modes or {}).values()
                ).items()
            )
        ),
        "candidateCount": len(candidates),
        "warmCandidateCount": len(warm_candidates),
        "categoryDistribution": _distribution(candidates),
        "businessHoursStatus": dict(
            sorted(Counter(str(item.business_hours_status) for item in candidates).items())
        ),
        "missingThumbnailCount": sum(
            item.thumbnail_url is None for item in candidates
        ),
        "missingAddressCount": sum(not item.address for item in candidates),
        "stadiumDuplicateCount": sum(
            item.name.replace(" ", "") == name.replace(" ", "")
            for item in candidates
        ),
        "diagnostics": diagnostics,
        "scheduledRecommendationCount": (
            itinerary.auto_recommended_place_count
        ),
        "supplementTargetDates": [
            target_date.isoformat() for target_date in supplement_dates
        ],
        "supplementalCandidateCount": len(supplemental_candidates),
        "scheduledByDay": {
            day.date.isoformat(): [
                item.place_id
                for item in day.items
                if item.added_by == "ALGORITHM"
            ]
            for day in itinerary.days
        },
        "scheduledItemsByDay": {
            day.date.isoformat(): [
                {
                    "placeId": item.place_id,
                    "name": item.name,
                    "category": item.category.value if item.category else None,
                    "scheduledStartAt": item.scheduled_start_at.isoformat(),
                    "scheduledEndAt": item.scheduled_end_at.isoformat(),
                    "travelMinutesFromPrevious": (
                        item.travel_minutes_from_previous
                    ),
                    "travelMode": (
                        item.travel_mode.value if item.travel_mode else None
                    ),
                    "travelTimeSource": (
                        item.travel_time_source.value
                        if item.travel_time_source
                        else None
                    ),
                }
                for item in day.items
            ]
            for day in itinerary.days
        },
        "placementRejectedAttempts": (
            itinerary.recommendation_summary.placement_rejected_attempts
            if itinerary.recommendation_summary is not None
            else {}
        ),
        "excludedPlaces": [
            item.model_dump(by_alias=True, mode="json")
            for item in itinerary.excluded_places
        ],
        "candidates": [
            {
                "placeId": item.place_id,
                "name": item.name,
                "category": str(item.category),
                "latitude": item.latitude,
                "longitude": item.longitude,
                "distanceMeters": item.distance_meters,
                "businessHoursStatus": str(item.business_hours_status),
                "lclsSystem1": item.lcls_system1,
                "lclsSystem2": item.lcls_system2,
                "lclsSystem3": item.lcls_system3,
            }
            for item in candidates
        ],
    }


async def main(
    output: Path,
    *,
    regions: list[str] | None = None,
    live_routes: bool = False,
    max_candidates: int = 20,
    travel_start_date: date = date(2026, 8, 15),
    nights: int = 2,
) -> None:
    calls = _install_call_counters()
    results = []
    selected = regions or list(STADIUMS)
    for label in selected:
        stadium = STADIUMS[label]
        try:
            result = await asyncio.wait_for(
                _inspect_region(
                    label,
                    stadium,
                    calls,
                    live_routes=live_routes,
                    max_candidates=max_candidates,
                    travel_start_date=travel_start_date,
                    nights=nights,
                ),
                timeout=90,
            )
        except Exception as exc:
            result = {
                "region": label,
                "error": f"{type(exc).__name__}: {exc}",
            }
        results.append(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(results, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(output.resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/recommendation-quality.json"),
    )
    parser.add_argument(
        "--region",
        action="append",
        choices=tuple(STADIUMS),
        dest="regions",
        help="검증할 지역입니다. 여러 번 지정할 수 있으며 생략하면 전체입니다.",
    )
    parser.add_argument(
        "--live-routes",
        action="store_true",
        help="직선거리 추정 대신 Kakao 실제 경로를 사용합니다.",
    )
    parser.add_argument(
        "--max-candidates",
        type=int,
        default=20,
        help="일정 배치에 전달할 최대 후보 수입니다.",
    )
    parser.add_argument(
        "--start-date",
        type=date.fromisoformat,
        default=date(2026, 8, 15),
        help="여행 시작일(YYYY-MM-DD)입니다.",
    )
    parser.add_argument(
        "--nights",
        type=int,
        default=2,
        choices=range(1, 8),
        metavar="1-7",
        help="여행 박수입니다. 3박 4일은 3을 지정합니다.",
    )
    arguments = parser.parse_args()
    asyncio.run(
        main(
            arguments.output,
            regions=arguments.regions,
            live_routes=arguments.live_routes,
            max_candidates=arguments.max_candidates,
            travel_start_date=arguments.start_date,
            nights=arguments.nights,
        )
    )

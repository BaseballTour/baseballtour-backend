"""TourAPI 엔드포인트별 연결 상태와 지연시간을 안전하게 진단한다."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
from dataclasses import asdict, dataclass
from time import monotonic
from typing import Awaitable, Callable

import httpx

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.external.tour_api.client import (
    extract_items,
    get_nearby_places,
    get_place_common_info,
    get_place_images,
    get_place_intro_info,
    search_places_by_keyword,
)


@dataclass
class CheckResult:
    scenario: str
    endpoint: str
    attempt: int
    outcome: str
    elapsed_ms: int
    item_count: int | None = None
    error_code: str | None = None
    timeout_type: str | None = None
    provider_code: str | None = None
    provider_message: str | None = None
    message: str | None = None


async def _measure(
    *,
    scenario: str,
    endpoint: str,
    attempt: int,
    operation: Callable[[], Awaitable[dict]],
) -> CheckResult:
    started_at = monotonic()
    try:
        data = await operation()
        return CheckResult(
            scenario=scenario,
            endpoint=endpoint,
            attempt=attempt,
            outcome="SUCCESS",
            elapsed_ms=round((monotonic() - started_at) * 1000),
            item_count=len(extract_items(data)),
        )
    except AppException as exc:
        details = exc.details if isinstance(exc.details, dict) else {}
        return CheckResult(
            scenario=scenario,
            endpoint=endpoint,
            attempt=attempt,
            outcome="FAILED",
            elapsed_ms=round((monotonic() - started_at) * 1000),
            error_code=exc.code,
            timeout_type=details.get("timeoutType"),
            provider_code=details.get("providerCode"),
            provider_message=details.get("providerMessage"),
            message=exc.message,
        )
    except Exception as exc:  # 진단 도구이므로 다음 시나리오를 계속한다.
        return CheckResult(
            scenario=scenario,
            endpoint=endpoint,
            attempt=attempt,
            outcome="FAILED",
            elapsed_ms=round((monotonic() - started_at) * 1000),
            error_code=type(exc).__name__,
            message=str(exc),
        )


async def run_diagnostics(args: argparse.Namespace) -> list[CheckResult]:
    results: list[CheckResult] = []
    timeout = httpx.Timeout(
        connect=args.connect_timeout,
        read=args.read_timeout,
        write=5.0,
        pool=5.0,
    )
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(1, args.repeat + 1):
            nearby = await _measure(
                scenario="nearby",
                endpoint="locationBasedList2",
                attempt=attempt,
                operation=lambda: get_nearby_places(
                    longitude=args.longitude,
                    latitude=args.latitude,
                    radius=args.radius,
                    num_of_rows=5,
                    client=client,
                ),
            )
            results.append(nearby)
            results.append(
                await _measure(
                    scenario="keyword",
                    endpoint="searchKeyword2",
                    attempt=attempt,
                    operation=lambda: search_places_by_keyword(
                        args.keyword,
                        num_of_rows=5,
                        client=client,
                    ),
                )
            )
            results.append(
                await _measure(
                    scenario="detail_common",
                    endpoint="detailCommon2",
                    attempt=attempt,
                    operation=lambda: get_place_common_info(
                        args.content_id, client=client
                    ),
                )
            )
            results.append(
                await _measure(
                    scenario="detail_intro",
                    endpoint="detailIntro2",
                    attempt=attempt,
                    operation=lambda: get_place_intro_info(
                        args.content_id,
                        args.content_type_id,
                        client=client,
                    ),
                )
            )
            results.append(
                await _measure(
                    scenario="detail_image",
                    endpoint="detailImage2",
                    attempt=attempt,
                    operation=lambda: get_place_images(
                        args.content_id, client=client
                    ),
                )
            )
    return results


def _summary(results: list[CheckResult]) -> dict[str, object]:
    elapsed = [item.elapsed_ms for item in results]
    failures: dict[str, int] = {}
    for item in results:
        if item.outcome == "FAILED":
            key = item.timeout_type or item.error_code or "UNKNOWN"
            failures[key] = failures.get(key, 0) + 1
    return {
        "requests": len(results),
        "successes": sum(item.outcome == "SUCCESS" for item in results),
        "failures": failures,
        "latencyMs": {
            "min": min(elapsed) if elapsed else None,
            "median": round(statistics.median(elapsed)) if elapsed else None,
            "max": max(elapsed) if elapsed else None,
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--longitude", type=float, default=127.0767)
    parser.add_argument("--latitude", type=float, default=37.5101)
    parser.add_argument("--radius", type=int, default=2000)
    parser.add_argument("--keyword", default="아시아공원")
    parser.add_argument("--content-id", default="1603175")
    parser.add_argument("--content-type-id", default="12")
    parser.add_argument("--connect-timeout", type=float, default=5.0)
    parser.add_argument("--read-timeout", type=float, default=10.0)
    parser.add_argument(
        "--bypass-cache",
        action="store_true",
        help="Firestore 공유 캐시를 사용하지 않고 실제 TourAPI 상태를 확인합니다.",
    )
    return parser.parse_args()


async def main() -> None:
    args = _parse_args()
    if args.bypass_cache:
        get_settings().tour_api_persistent_cache_enabled = False
    results = await run_diagnostics(args)
    print(json.dumps(
        {
            "results": [asdict(item) for item in results],
            "summary": _summary(results),
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    asyncio.run(main())

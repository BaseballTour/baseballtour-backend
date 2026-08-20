from time import monotonic
from typing import Any

import httpx

from app.core.config import get_settings


ODSAY_TRANSIT_URL = (
    "https://api.odsay.com/v1/api/searchPubTransPathT"
)
TRANSIT_CACHE_TTL_SECONDS = 300
_transit_cache: dict[
    tuple[float, float, float, float],
    tuple[float, int],
] = {}


def _format_odsay_error(error: Any) -> str:
    """API 키를 제외한 ODsay 오류 코드와 메시지만 로그용으로 정리한다."""
    item = error[0] if isinstance(error, list) and error else error
    if not isinstance(item, dict):
        return "unknown"

    code = str(item.get("code", "unknown")).strip()
    message = str(
        item.get("message") or item.get("msg") or "unknown"
    ).strip()
    # 외부 문자열의 개행과 과도한 길이가 로그를 오염시키지 않게 제한한다.
    message = " ".join(message.split())[:200]
    return f"code={code} message={message}"


def parse_transit_minutes(data: Any) -> int:
    if not isinstance(data, dict):
        raise ValueError("ODsay 응답 형식이 올바르지 않습니다.")
    if data.get("error"):
        raise ValueError(
            "ODsay가 오류 응답을 반환했습니다: "
            f"{_format_odsay_error(data['error'])}"
        )

    paths = data.get("result", {}).get("path", [])
    if not isinstance(paths, list):
        raise ValueError("ODsay 이동시간 응답에 경로가 없습니다.")
    minutes = [
        path.get("info", {}).get("totalTime")
        for path in paths
        if isinstance(path, dict)
    ]
    valid = [value for value in minutes if isinstance(value, int)]
    if not valid:
        raise ValueError("ODsay 이동시간 응답에 경로가 없습니다.")
    return min(valid)


async def get_transit_minutes(
    origin_longitude: float,
    origin_latitude: float,
    destination_longitude: float,
    destination_latitude: float,
    *,
    client: httpx.AsyncClient | None = None,
) -> int:
    api_key = get_settings().odsay_api_key.strip()
    if not api_key:
        raise RuntimeError("ODsay API 키가 설정되지 않았습니다.")

    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=10.0)
    try:
        response = await active_client.get(
            ODSAY_TRANSIT_URL,
            params={
                "SX": origin_longitude,
                "SY": origin_latitude,
                "EX": destination_longitude,
                "EY": destination_latitude,
                "apiKey": api_key,
            },
        )
        response.raise_for_status()
        data: Any = response.json()
    finally:
        if owns_client:
            await active_client.aclose()

    return parse_transit_minutes(data)


async def get_cached_transit_minutes(
    origin_longitude: float,
    origin_latitude: float,
    destination_longitude: float,
    destination_latitude: float,
) -> int:
    key = tuple(
        round(value, 6)
        for value in (
            origin_longitude,
            origin_latitude,
            destination_longitude,
            destination_latitude,
        )
    )
    now = monotonic()
    cached = _transit_cache.get(key)
    if cached is not None and cached[0] > now:
        return cached[1]

    minutes = await get_transit_minutes(
        origin_longitude,
        origin_latitude,
        destination_longitude,
        destination_latitude,
    )
    _transit_cache[key] = (
        now + TRANSIT_CACHE_TTL_SECONDS,
        minutes,
    )
    return minutes

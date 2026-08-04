from typing import Any

import httpx

from app.core.config import get_settings


ODSAY_TRANSIT_URL = (
    "https://api.odsay.com/v1/api/searchPubTransPathT"
)


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

    paths = data.get("result", {}).get("path", [])
    minutes = [
        path.get("info", {}).get("totalTime")
        for path in paths
        if isinstance(path, dict)
    ]
    valid = [value for value in minutes if isinstance(value, int)]
    if not valid:
        raise ValueError("ODsay 이동시간 응답에 경로가 없습니다.")
    return min(valid)

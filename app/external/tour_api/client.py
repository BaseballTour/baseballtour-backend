from typing import Any

import httpx

from app.core.config import get_settings
from app.models.place import Place
from app.external.tour_api.mapper import tour_api_items_to_places


TOUR_API_BASE_URL = (
    "https://apis.data.go.kr/B551011/KorService2/locationBasedList2"
)


async def get_nearby_places(
    longitude: float,
    latitude: float,
    radius: int = 2000,
    page_no: int = 1,
    num_of_rows: int = 20,
) -> dict[str, Any]:
    """
    지정한 좌표 주변의 관광 장소를 TourAPI에서 조회한다.

    longitude: 경도(mapX)
    latitude: 위도(mapY)
    radius: 검색 반경(미터), 최대 허용 범위는 API 명세를 따름
    """

    settings = get_settings()

    params = {
        "serviceKey": settings.tour_api_key,
        "MobileOS": "ETC",
        "MobileApp": "BaseballTour",
        "_type": "json",
        "mapX": longitude,
        "mapY": latitude,
        "radius": radius,
        "arrange": "E",
        "pageNo": page_no,
        "numOfRows": num_of_rows,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                TOUR_API_BASE_URL,
                params=params,
            )

            response.raise_for_status()

    except httpx.TimeoutException as exc:
        raise RuntimeError("TourAPI 요청 시간이 초과되었습니다.") from exc

    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"TourAPI HTTP 오류가 발생했습니다: "
            f"{exc.response.status_code}"
        ) from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise RuntimeError(
            f"TourAPI가 JSON이 아닌 응답을 반환했습니다: "
            f"{response.text[:300]}"
        ) from exc

    return data

async def get_nearby_place_list(
    longitude: float,
    latitude: float,
    radius: int = 2000,
    page_no: int = 1,
    num_of_rows: int = 20,
) -> list[Place]:
    raw_data = await get_nearby_places(
        longitude=longitude,
        latitude=latitude,
        radius=radius,
        page_no=page_no,
        num_of_rows=num_of_rows,
    )

    items = (
        raw_data
        .get("response", {})
        .get("body", {})
        .get("items", {})
        .get("item", [])
    )

    return tour_api_items_to_places(items)
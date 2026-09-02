from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.exceptions import AppException


KAKAO_LOCAL_BASE_URL = "https://dapi.kakao.com/v2/local"


@dataclass(frozen=True)
class KakaoPlacePage:
    documents: list[dict[str, Any]]
    is_end: bool


async def _request_kakao_local(
    path: str,
    *,
    params: dict[str, Any],
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Kakao Local API 공통 인증·오류 처리를 수행합니다."""

    api_key = get_settings().kakao_rest_api_key.strip()
    if not api_key:
        raise AppException(
            status_code=503,
            code="EXTERNAL_API_UNAVAILABLE",
            message="Kakao Local API 키가 설정되지 않았습니다.",
        )

    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=5.0)
    try:
        response = await active_client.get(
            f"{KAKAO_LOCAL_BASE_URL}/{path}",
            headers={"Authorization": f"KakaoAK {api_key}"},
            params=params,
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise AppException(
            status_code=503,
            code="EXTERNAL_API_TIMEOUT",
            message="Kakao Local API 요청 시간이 초과되었습니다.",
        ) from exc
    except httpx.HTTPStatusError as exc:
        error_type = ""
        error_message = ""
        try:
            error_data = exc.response.json()
            if isinstance(error_data, dict):
                error_type = str(error_data.get("errorType") or "").strip()
                error_message = str(error_data.get("message") or "").strip()
        except ValueError:
            pass
        api_disabled = (
            exc.response.status_code == 403
            and "disabled OPEN_MAP_AND_LOCAL service" in error_message
        )
        raise AppException(
            status_code=503,
            code=(
                "KAKAO_LOCAL_API_NOT_ENABLED"
                if api_disabled
                else "EXTERNAL_API_UNAVAILABLE"
            ),
            message=(
                "Kakao Developers에서 카카오맵 API를 활성화해야 합니다."
                if api_disabled
                else "Kakao Local API를 일시적으로 사용할 수 없습니다."
            ),
            details={
                "statusCode": exc.response.status_code,
                "errorType": error_type,
            },
        ) from exc
    except httpx.RequestError as exc:
        raise AppException(
            status_code=503,
            code="EXTERNAL_API_UNAVAILABLE",
            message="Kakao Local API 연결에 실패했습니다.",
        ) from exc
    finally:
        if owns_client:
            await active_client.aclose()

    try:
        data = response.json()
    except ValueError as exc:
        raise AppException(
            status_code=502,
            code="EXTERNAL_API_INVALID_RESPONSE",
            message="Kakao Local API가 JSON이 아닌 응답을 반환했습니다.",
        ) from exc
    if not isinstance(data, dict):
        raise AppException(
            status_code=502,
            code="EXTERNAL_API_INVALID_RESPONSE",
            message="Kakao Local API 응답 형식이 올바르지 않습니다.",
        )
    return data


async def search_place_page(
    query: str,
    *,
    longitude: float | None = None,
    latitude: float | None = None,
    radius: int = 20_000,
    page: int = 1,
    size: int = 15,
    category_group_code: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> KakaoPlacePage:
    params: dict[str, Any] = {
        "query": query,
        "page": page,
        "size": size,
    }
    if longitude is not None and latitude is not None:
        params.update(
            {
                "x": longitude,
                "y": latitude,
                "radius": radius,
                "sort": "distance",
            }
        )
    if category_group_code:
        params["category_group_code"] = category_group_code

    data = await _request_kakao_local(
        "search/keyword.json",
        params=params,
        client=client,
    )
    documents = data.get("documents")
    meta = data.get("meta", {})
    if not isinstance(documents, list) or not isinstance(meta, dict):
        raise AppException(
            status_code=502,
            code="EXTERNAL_API_INVALID_RESPONSE",
            message="Kakao Local API 응답 형식이 올바르지 않습니다.",
        )
    return KakaoPlacePage(
        documents=[item for item in documents if isinstance(item, dict)],
        is_end=bool(meta.get("is_end", True)),
    )


async def search_places_by_keyword(
    query: str,
    *,
    longitude: float,
    latitude: float,
    radius: int = 500,
    size: int = 5,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """좌표 주변에서 이름이 일치하는 카카오 장소 후보를 조회한다."""
    result = await search_place_page(
        query,
        longitude=longitude,
        latitude=latitude,
        radius=radius,
        size=size,
        client=client,
    )
    return result.documents


async def reverse_geocode(
    *,
    longitude: float,
    latitude: float,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """지도에서 선택한 좌표를 도로명·지번 주소로 변환합니다."""

    data = await _request_kakao_local(
        "geo/coord2address.json",
        params={"x": longitude, "y": latitude, "input_coord": "WGS84"},
        client=client,
    )
    documents = data.get("documents")
    if not isinstance(documents, list):
        raise AppException(
            status_code=502,
            code="EXTERNAL_API_INVALID_RESPONSE",
            message="Kakao Local API 응답 형식이 올바르지 않습니다.",
        )
    return [item for item in documents if isinstance(item, dict)]


async def geocode_address(
    address: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """도로명·지번 주소를 좌표 후보로 변환합니다."""

    data = await _request_kakao_local(
        "search/address.json",
        params={"query": address},
        client=client,
    )
    documents = data.get("documents")
    if not isinstance(documents, list):
        raise AppException(
            status_code=502,
            code="EXTERNAL_API_INVALID_RESPONSE",
            message="Kakao Local 주소 검색 응답 형식이 올바르지 않습니다.",
        )
    return [item for item in documents if isinstance(item, dict)]

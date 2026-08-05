from typing import Any

import httpx

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.external.tour_api.mapper import tour_api_items_to_places
from app.models.place import Place


TOUR_API_BASE_URL = "https://apis.data.go.kr/B551011/KorService2"
TOUR_API_SUCCESS_CODE = "0000"

TOUR_API_RATE_LIMIT_CODES = {
    "22",
}

TOUR_API_RATE_LIMIT_MESSAGES = {
    "LIMITED NUMBER OF SERVICE REQUESTS EXCEEDS",
}


def _extract_root_error(data: dict[str, Any]) -> tuple[str, str] | None:
    """공공데이터포털 게이트웨이의 response 없는 오류를 추출한다."""
    result_code = data.get("resultCode")
    result_message = data.get("resultMsg") or data.get("resultMessage")
    if result_code is not None or result_message is not None:
        return (
            str(result_code or "").strip(),
            str(result_message or "").strip(),
        )

    service_response = data.get("OpenAPI_ServiceResponse")
    if not isinstance(service_response, dict):
        return None

    header = service_response.get("cmmMsgHeader")
    if not isinstance(header, dict):
        return None

    return (
        str(header.get("returnReasonCode", "")).strip(),
        str(
            header.get("returnAuthMsg")
            or header.get("errMsg")
            or ""
        ).strip(),
    )


def _common_params() -> dict[str, Any]:
    service_key = get_settings().tour_api_key.strip()

    if not service_key:
        raise AppException(
            status_code=503,
            code="EXTERNAL_API_UNAVAILABLE",
            message="TourAPI 서비스 키가 설정되지 않았습니다.",
        )

    return {
        "serviceKey": service_key,
        "MobileOS": "ETC",
        "MobileApp": "BaseballTour",
        "_type": "json",
    }


def _validate_tour_api_response(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise AppException(
            status_code=502,
            code="EXTERNAL_API_INVALID_RESPONSE",
            message="TourAPI 응답 형식이 올바르지 않습니다.",
        )

    response = data.get("response")
    if not isinstance(response, dict):
        root_error = _extract_root_error(data)
        if root_error is not None:
            result_code, result_message = root_error
            normalized_message = result_message.upper()
            is_rate_limited = (
                result_code in TOUR_API_RATE_LIMIT_CODES
                or any(
                    message in normalized_message
                    for message in TOUR_API_RATE_LIMIT_MESSAGES
                )
            )
            raise AppException(
                status_code=429 if is_rate_limited else 502,
                code=(
                    "EXTERNAL_API_RATE_LIMITED"
                    if is_rate_limited
                    else "TOUR_API_FAILED"
                ),
                message=(
                    "TourAPI 호출 제한을 초과했습니다."
                    if is_rate_limited
                    else "TourAPI 요청 처리에 실패했습니다."
                ),
                details={
                    "resultCode": result_code,
                    "resultMessage": result_message,
                },
            )
        raise AppException(
            status_code=502,
            code="EXTERNAL_API_INVALID_RESPONSE",
            message="TourAPI 응답에 response 객체가 없습니다.",
        )

    header = response.get("header")
    if not isinstance(header, dict):
        raise AppException(
            status_code=502,
            code="EXTERNAL_API_INVALID_RESPONSE",
            message="TourAPI 응답 헤더가 올바르지 않습니다.",
        )

    result_code = str(
    header.get("resultCode", "")
    ).strip()

    result_message = str(
        header.get("resultMsg", "")
    ).strip()

    normalized_message = result_message.upper()

    is_rate_limited = (
        result_code in TOUR_API_RATE_LIMIT_CODES
        or any(
            message in normalized_message
            for message in TOUR_API_RATE_LIMIT_MESSAGES
        )
    )

    if is_rate_limited:
        raise AppException(
            status_code=429,
            code="EXTERNAL_API_RATE_LIMITED",
            message="TourAPI 호출 제한을 초과했습니다.",
            details={
                "resultCode": result_code,
                "resultMessage": result_message,
            },
        )

    if result_code != TOUR_API_SUCCESS_CODE:
        raise AppException(
            status_code=502,
            code="TOUR_API_FAILED",
            message="TourAPI 요청 처리에 실패했습니다.",
            details={
                "resultCode": result_code,
                "resultMessage": result_message,
            },
        )

    return data


async def _request_tour_api(
    endpoint: str,
    params: dict[str, Any],
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    request_params = _common_params()
    request_params.update(params)
    owns_client = client is None
    active_client = client or httpx.AsyncClient(timeout=15.0)

    try:
        response = await active_client.get(
            f"{TOUR_API_BASE_URL}/{endpoint}",
            params=request_params,
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise AppException(
            status_code=503,
            code="EXTERNAL_API_TIMEOUT",
            message="TourAPI 요청 시간이 초과되었습니다.",
        ) from exc
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        error_code = (
            "EXTERNAL_API_RATE_LIMITED"
            if status_code == 429
            else "EXTERNAL_API_UNAVAILABLE"
        )
        raise AppException(
            status_code=503 if status_code != 429 else 429,
            code=error_code,
            message="TourAPI를 일시적으로 사용할 수 없습니다.",
        ) from exc
    except httpx.RequestError as exc:
        raise AppException(
            status_code=503,
            code="EXTERNAL_API_UNAVAILABLE",
            message="TourAPI 연결에 실패했습니다.",
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
            message="TourAPI가 JSON이 아닌 응답을 반환했습니다.",
        ) from exc

    return _validate_tour_api_response(data)


def extract_items(data: dict[str, Any]) -> list[dict[str, Any]]:
    body = data.get("response", {}).get("body", {})
    if not isinstance(body, dict):
        return []

    items = body.get("items")
    if not isinstance(items, dict):
        return []

    item = items.get("item", [])
    if isinstance(item, dict):
        return [item]
    if not isinstance(item, list):
        return []

    return [value for value in item if isinstance(value, dict)]


async def get_nearby_places(
    longitude: float,
    latitude: float,
    radius: int = 2000,
    page_no: int = 1,
    num_of_rows: int = 20,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    return await _request_tour_api(
        "locationBasedList2",
        {
            "mapX": longitude,
            "mapY": latitude,
            "radius": radius,
            "arrange": "E",
            "pageNo": page_no,
            "numOfRows": num_of_rows,
        },
        client=client,
    )


async def get_place_common_info(
    content_id: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    return await _request_tour_api(
        "detailCommon2",
        {
            "contentId": content_id,
        },
        client=client,
    )


async def get_place_intro_info(
    content_id: str,
    content_type_id: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    return await _request_tour_api(
        "detailIntro2",
        {
            "contentId": content_id,
            "contentTypeId": content_type_id,
        },
        client=client,
    )


async def get_place_images(
    content_id: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    return await _request_tour_api(
        "detailImage2",
        {
            "contentId": content_id,
            "imageYN": "Y",
            "numOfRows": 20,
            "pageNo": 1,
        },
        client=client,
    )


async def get_nearby_place_list(
    longitude: float,
    latitude: float,
    radius: int = 2000,
    page_no: int = 1,
    num_of_rows: int = 20,
    *,
    client: httpx.AsyncClient | None = None,
) -> list[Place]:
    raw_data = await get_nearby_places(
        longitude=longitude,
        latitude=latitude,
        radius=radius,
        page_no=page_no,
        num_of_rows=num_of_rows,
        client=client,
    )
    return tour_api_items_to_places(extract_items(raw_data))

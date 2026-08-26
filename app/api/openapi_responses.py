"""Swagger에 표시할 공통·도메인별 오류 응답 예시."""

from typing import Any

from app.schemas.response import ErrorResponse


def _example(code: str, message: str, details: list[Any] | None = None) -> dict:
    return {
        "value": {
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": details or [],
            },
        }
    }


def _response(description: str, **examples: dict) -> dict:
    return {
        "model": ErrorResponse,
        "description": description,
        "content": {"application/json": {"examples": examples}},
    }


AUTH_ERROR_RESPONSES = {
    401: _response(
        "Firebase 인증 실패",
        token_missing=_example("AUTH_TOKEN_MISSING", "인증 토큰이 필요합니다."),
        token_invalid=_example("AUTH_TOKEN_INVALID", "인증 토큰이 올바르지 않습니다."),
        token_expired=_example("AUTH_TOKEN_EXPIRED", "인증 토큰이 만료되었습니다."),
        token_revoked=_example("AUTH_TOKEN_REVOKED", "폐기된 인증 토큰입니다."),
    ),
    403: _response(
        "접근 권한 없음",
        access_denied=_example("TRIP_ACCESS_DENIED", "해당 여행에 접근할 권한이 없습니다."),
    ),
}


BASE_API_ERROR_RESPONSES = {
    422: _response(
        "요청 필드 검증 실패",
        validation_error=_example(
            "VALIDATION_ERROR",
            "입력값을 확인해 주세요.",
            [{"field": "scheduledStartAt", "reason": "Input should be a valid datetime"}],
        ),
    ),
    500: _response(
        "처리되지 않은 서버 오류",
        internal_error=_example("INTERNAL_SERVER_ERROR", "서버 내부 오류가 발생했습니다."),
    ),
}


COMMON_API_ERROR_RESPONSES = {
    **BASE_API_ERROR_RESPONSES,
    **AUTH_ERROR_RESPONSES,
}


TOUR_API_ERROR_RESPONSES = {
    400: _response(
        "장소 검색 요청 오류",
        invalid_page_token=_example("INVALID_PAGE_TOKEN", "페이지 토큰 형식이 올바르지 않습니다."),
        invalid_place_id=_example("INVALID_PLACE_ID", "TourAPI 장소 ID 형식이 올바르지 않습니다."),
    ),
    429: _response(
        "TourAPI 호출 한도 초과",
        rate_limited=_example("EXTERNAL_API_RATE_LIMITED", "TourAPI 호출 제한을 초과했습니다."),
    ),
    502: _response(
        "TourAPI 오류 응답",
        invalid_response=_example("EXTERNAL_API_INVALID_RESPONSE", "TourAPI 응답 형식이 올바르지 않습니다."),
        tour_api_failed=_example("TOUR_API_FAILED", "TourAPI 요청 처리에 실패했습니다."),
    ),
    503: _response(
        "TourAPI 연결 실패",
        timeout=_example("EXTERNAL_API_TIMEOUT", "TourAPI 요청 시간이 초과되었습니다."),
        unavailable=_example("EXTERNAL_API_UNAVAILABLE", "TourAPI를 일시적으로 사용할 수 없습니다."),
    ),
}


FAVORITE_ERROR_RESPONSES = {
    **AUTH_ERROR_RESPONSES,
    404: _response(
        "컬렉션 또는 찜 장소 없음",
        collection_not_found=_example("FAVORITE_COLLECTION_NOT_FOUND", "찜 컬렉션을 찾을 수 없습니다."),
        item_not_found=_example("FAVORITE_COLLECTION_ITEM_NOT_FOUND", "찜한 장소를 찾을 수 없습니다."),
    ),
    422: _response(
        "요청 검증 또는 지원하지 않는 장소",
        validation_error=_example("VALIDATION_ERROR", "입력값을 확인해 주세요."),
        invalid_place=_example("INVALID_FAVORITE_PLACE", "TourAPI 장소만 찜할 수 있습니다."),
    ),
    502: TOUR_API_ERROR_RESPONSES[502],
    503: TOUR_API_ERROR_RESPONSES[503],
}


TRIP_ERROR_RESPONSES = {
    **AUTH_ERROR_RESPONSES,
    400: _response(
        "여행·일정 요청 규칙 위반",
        trip_time_invalid=_example("TRIP_TIME_INVALID", "여행 종료 시간은 시작 시간보다 늦어야 합니다."),
        game_outside_period=_example("GAME_OUTSIDE_TRIP_PERIOD", "경기 시간이 여행 기간에 포함되어야 합니다."),
        itinerary_input_invalid=_example("ITINERARY_INPUT_INVALID", "일정 생성 입력값이 올바르지 않습니다."),
        itinerary_edit_invalid=_example("ITINERARY_EDIT_INVALID", "일정 항목을 수정할 수 없습니다."),
        anchor_not_editable=_example("ITINERARY_ANCHOR_NOT_EDITABLE", "Anchor 시간은 이 API에서 변경할 수 없습니다."),
        item_date_mismatch=_example("ITINERARY_ITEM_DATE_MISMATCH", "date와 scheduledStartAt의 날짜가 일치해야 합니다."),
    ),
    404: _response(
        "여행·일정 리소스 없음",
        trip_not_found=_example("TRIP_NOT_FOUND", "여행 정보를 찾을 수 없습니다."),
        game_not_found=_example("GAME_NOT_FOUND", "경기 정보를 찾을 수 없습니다."),
        plan_not_found=_example("ITINERARY_PLAN_NOT_FOUND", "현재 활성화된 여행 일정이 없습니다."),
        day_not_found=_example("ITINERARY_DAY_NOT_FOUND", "수정할 날짜의 일정을 찾을 수 없습니다."),
        item_not_found=_example("ITINERARY_ITEM_NOT_FOUND", "수정할 일정 항목을 찾을 수 없습니다."),
        place_not_found=_example("ITINERARY_PLACE_NOT_FOUND", "추가할 장소 정보를 찾을 수 없습니다."),
        selection_not_found=_example("PLACE_SELECTION_NOT_FOUND", "선택한 장소를 찾을 수 없습니다."),
    ),
    409: _response(
        "현재 상태 또는 기존 데이터와 충돌",
        generation_in_progress=_example("TRIP_GENERATION_IN_PROGRESS", "일정 생성이 이미 진행 중입니다."),
        place_exists=_example("ITINERARY_PLACE_ALREADY_EXISTS", "해당 장소가 이미 일정에 포함되어 있습니다."),
        selection_exists=_example("PLACE_SELECTION_ALREADY_EXISTS", "이미 선택된 장소입니다."),
        idempotency_conflict=_example("TRIP_IDEMPOTENCY_CONFLICT", "같은 멱등성 키가 다른 요청에 사용되었습니다."),
    ),
    429: TOUR_API_ERROR_RESPONSES[429],
    502: TOUR_API_ERROR_RESPONSES[502],
    503: TOUR_API_ERROR_RESPONSES[503],
}


def merge_responses(*groups: dict[int, dict]) -> dict[int, dict]:
    """뒤에 전달한 도메인 응답이 같은 상태의 공통 응답을 대체합니다."""

    merged: dict[int, dict] = {}
    for group in groups:
        merged.update(group)
    return merged

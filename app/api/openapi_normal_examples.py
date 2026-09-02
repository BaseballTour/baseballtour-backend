"""프론트 연동용 정상 요청·응답 및 파라미터 Swagger 예시."""

from copy import deepcopy
from typing import Any

from fastapi import FastAPI


PLACE = {
    "placeId": "tour_1603175", "name": "아시아공원",
    "category": "TOURIST_SPOT", "latitude": 37.510082,
    "longitude": 127.076703, "address": "서울특별시 송파구 올림픽로 44",
    "postalCode": "05572", "telephone": None,
    "thumbnailUrl": "https://example.com/asia-park.jpg",
    "overview": "잠실종합운동장 인근에서 산책하기 좋은 공원입니다.",
    "openTime": None, "closeTime": None,
    "businessHoursStatus": "MISSING", "businessHoursText": None,
    "businessHoursRules": [], "admissionDeadlineTime": None,
    "admissionDeadlineStatus": "MISSING", "admissionDeadlineText": None,
    "closedDaysText": None, "closedDaysStatus": "MISSING",
    "closedWeekdays": [], "eventStartDate": None, "eventEndDate": None,
    "defaultStayMinutes": 60, "distanceMeters": 487.4,
    "source": "TOUR_API", "sourceContentId": "1603175",
    "kakaoPlaceId": None, "enrichedBy": [],
    "contentTypeId": "12", "lclsSystem1": "VE",
    "lclsSystem2": "VE01", "lclsSystem3": "VE010100",
}
GAME = {
    "gameId": "game_20260816_kiwoom_lg",
    "gameStartAt": "2026-08-16T17:00:00+09:00", "status": "SCHEDULED",
    "homeTeam": {"teamId": "kiwoom", "name": "키움 히어로즈", "logoUrl": None},
    "awayTeam": {"teamId": "lg", "name": "LG 트윈스", "logoUrl": None},
    "stadium": {"stadiumId": "gocheok", "name": "고척스카이돔",
                "address": "서울특별시 구로구 경인로 430",
                "latitude": 37.4982, "longitude": 126.8671},
    "homeScore": None, "awayScore": None, "resultText": None,
}
TRIP_SUMMARY = {
    "tripId": "trip_001", "gameId": GAME["gameId"],
    "title": "고척 원정 1박 2일",
    "subtitle": "2026.08.16 ~ 2026.08.17",
    "status": "GENERATED",
    "tripStartAt": "2026-08-16T12:00:00+09:00",
    "tripEndAt": "2026-08-17T23:00:00+09:00",
    "createdAt": "2026-08-15T10:00:00+09:00",
}
TRIP_DETAIL = {
    **TRIP_SUMMARY,
    "arrivalPoint": {"name": "서울역", "latitude": 37.5547, "longitude": 126.9706},
    "departurePoint": {"name": "서울역", "latitude": 37.5547, "longitude": 126.9706},
    "accommodation": {
        "accommodationId": "accommodation_kakao_123456789",
        "name": "고척 예시 호텔",
        "address": "서울특별시 구로구 경인로 00",
        "latitude": 37.4985, "longitude": 126.868,
    },
    "travelStyle": "BALANCED", "scheduleDensity": "MODERATE",
    "activePlanId": "plan_001",
    "updatedAt": "2026-08-15T11:00:00+09:00",
}
PLAN = {
    "planId": "plan_001", "tripId": "trip_001", "status": "ACTIVE",
    "algorithmVersion": "auto-fill-v0.5", "totalTravelMinutes": 25,
    "totalTravelDistanceMeters": 8400,
    "days": [{"date": "2026-08-16", "dayType": "GAME_DAY", "items": [{
        "itemId": "item_1_1", "type": "PLACE", "sequence": 1,
        "placeId": PLACE["placeId"], "category": "TOURIST_SPOT",
        "thumbnailUrl": PLACE["thumbnailUrl"],
        "shortDescription": "잠실종합운동장 인근 산책 장소",
        "overview": PLACE["overview"],
        "name": PLACE["name"], "address": PLACE["address"],
        "latitude": PLACE["latitude"], "longitude": PLACE["longitude"],
        "scheduledStartAt": "2026-08-16T13:00:00+09:00",
        "scheduledEndAt": "2026-08-16T14:00:00+09:00",
        "travelMinutesFromPrevious": 25, "transferBufferMinutes": 15,
        "travelDistanceMetersFromPrevious": 8400,
        "travelMode": "TRANSIT", "travelTimeSource": "KAKAO",
        "isRequired": False, "addedBy": "ALGORITHM", "isFixed": False,
    }]}],
    "excludedPlaces": [],
    "recommendationSummary": {"fetchedCount": 20, "candidateCount": 12,
        "scheduledCount": 1, "categoryDistribution": {"TOURIST_SPOT": 1},
        "filteredCounts": {}, "placementRejectedAttempts": {}},
}
USER = {
    "userId": "firebase_uid_example", "email": "user@example.com",
    "nickname": "민준", "birthYear": 2002, "profileImageUrl": None,
    "supportTeam": {"teamId": "lg", "name": "LG 트윈스",
                    "logoUrl": "https://example.com/lg.png"},
    "onboardingCompleted": True, "createdAt": "2026-08-12T15:00:00+09:00",
    "updatedAt": "2026-08-12T15:00:00+09:00",
}
ACCOMMODATION_CANDIDATE = {
    "accommodationId": "accommodation_kakao_123456789",
    "kakaoPlaceId": "123456789", "name": "잠실 예시 호텔",
    "address": "서울특별시 송파구 올림픽로 00",
    "roadAddressName": "서울특별시 송파구 올림픽로 00",
    "latitude": 37.5101, "longitude": 127.0767,
    "phone": "02-1234-5678",
    "placeUrl": "https://place.map.kakao.com/123456789",
    "categoryName": "여행 > 숙박 > 호텔",
    "selectionType": "KAKAO_PLACE",
}


def _success(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data}


def _list(data: list[Any]) -> dict[str, Any]:
    return {"success": True, "data": data,
            "meta": {"count": len(data), "nextPageToken": None}}


REQUEST_EXAMPLES = {
    ("post", "/api/v1/users/me/favorite-collections"): {"name": "고척 원정 후보"},
    ("patch", "/api/v1/users/me/favorite-collections/{collectionId}"): {"name": "서울 원정 맛집"},
    ("post", "/api/v1/trips"): {"gameId": GAME["gameId"], "title": "고척 원정 1박 2일",
        "tripStartAt": "2026-08-16T12:00:00+09:00",
        "tripEndAt": "2026-08-17T23:00:00+09:00",
        "arrivalPoint": TRIP_DETAIL["arrivalPoint"],
        "departurePoint": TRIP_DETAIL["departurePoint"],
        "accommodation": TRIP_DETAIL["accommodation"],
        "travelStyle": "BALANCED", "scheduleDensity": "MODERATE"},
    ("patch", "/api/v1/trips/{tripId}"): {"title": "수정한 고척 원정 여행"},
    ("post", "/api/v1/trips/{tripId}/place-selections"): {"placeId": PLACE["placeId"], "isRequired": True},
    ("post", "/api/v1/trips/{tripId}/place-selections/import"): {"collectionId": "collection_001"},
    ("patch", "/api/v1/trips/{tripId}/place-selections/{placeId}"): {"isRequired": True},
    ("patch", "/api/v1/trips/{tripId}/plan/items/order"): {"date": "2026-08-16", "itemIds": ["item_1_2", "item_1_1"]},
    ("post", "/api/v1/trips/{tripId}/plan/items"): {
        "placeId": PLACE["placeId"], "isRequired": True},
    ("patch", "/api/v1/trips/{tripId}/plan/items/{itemId}/fixed"): {"isFixed": True},
    ("patch", "/api/v1/trips/{tripId}/plan/items/{itemId}/time"): {"scheduledStartAt": "2026-08-17T14:00:00+09:00"},
    ("post", "/api/v1/users/me/bootstrap"): {"nickname": "민준", "birthYear": 2002, "supportTeamId": "lg"},
    ("patch", "/api/v1/users/me"): {"nickname": "민준"},
    ("patch", "/api/v1/users/me/support-team"): {"supportTeamId": "lg"},
    ("post", "/api/v1/users/me/term-agreements"): {"agreements": [
        {"termCode": "TERMS_OF_SERVICE", "version": "1.0", "agreed": True},
        {"termCode": "PRIVACY_POLICY", "version": "1.0", "agreed": True}]},
}
COLLECTION = {"collectionId": "collection_001", "name": "고척 원정 후보",
              "thumbnailUrl": PLACE["thumbnailUrl"],
              "createdAt": "2026-08-15T10:00:00+09:00",
              "updatedAt": "2026-08-15T10:00:00+09:00"}
SELECTION = {"placeId": PLACE["placeId"], "isRequired": True,
             "createdAt": "2026-08-15T10:10:00+09:00"}

SUCCESS_EXAMPLES = {
    ("get", "/api/v1/accommodations/search", "200"): _list([
        ACCOMMODATION_CANDIDATE
    ]),
    ("get", "/api/v1/accommodations/reverse-geocode", "200"): _success({
        **ACCOMMODATION_CANDIDATE,
        "accommodationId": "accommodation_map_0123456789abcdef",
        "kakaoPlaceId": None,
        "selectionType": "MAP_POINT",
    }),
    ("get", "/", "200"): _success({"name": "BaseballTour Backend", "environment": "development", "status": "running"}),
    ("get", "/api/v1/health", "200"): _success({"status": "healthy"}),
    ("get", "/api/v1/users/me/favorite-collections", "200"): _list([COLLECTION]),
    ("post", "/api/v1/users/me/favorite-collections", "201"): _success(COLLECTION),
    ("get", "/api/v1/users/me/favorite-collections/{collectionId}", "200"): _list([PLACE]),
    ("patch", "/api/v1/users/me/favorite-collections/{collectionId}", "200"): _success(COLLECTION),
    ("put", "/api/v1/users/me/favorite-collections/{collectionId}/items/{placeId}", "200"): _success({"placeId": PLACE["placeId"], "createdAt": "2026-08-15T10:10:00+09:00"}),
    (
        "get",
        "/api/v1/attendance-logs/{attendanceLogId}/itinerary",
        "200",
    ): _success({
        **PLAN,
        "status": "ARCHIVED",
    }),
    ("get", "/api/v1/games", "200"): _list([GAME]),
    ("get", "/api/v1/games/{gameId}", "200"): _success(GAME),
    ("get", "/api/v1/teams", "200"): _list([{"teamId": "lg", "name": "LG 트윈스", "shortName": "LG", "logoUrl": "https://example.com/lg.png", "homeRegion": "서울", "stadiumId": "jamsil"}]),
    ("get", "/api/v1/terms", "200"): _list([{"termCode": "TERMS_OF_SERVICE", "title": "서비스 이용약관", "required": True, "version": "1.0", "content": "약관 내용", "effectiveAt": "2026-08-01T00:00:00+09:00"}]),
    ("post", "/api/v1/trips", "201"): _success(TRIP_SUMMARY),
    ("get", "/api/v1/trips", "200"): _list([TRIP_SUMMARY]),
    ("get", "/api/v1/trips/{tripId}", "200"): _success(TRIP_DETAIL),
    ("patch", "/api/v1/trips/{tripId}", "200"): _success(TRIP_DETAIL),
    ("post", "/api/v1/trips/{tripId}/place-selections", "201"): _success(SELECTION),
    ("get", "/api/v1/trips/{tripId}/place-selections", "200"): _list([SELECTION]),
    ("get", "/api/v1/trips/{tripId}/recommendation-candidates", "200"): _list([PLACE]),
    ("post", "/api/v1/trips/{tripId}/place-selections/import", "200"): _list([SELECTION]),
    ("patch", "/api/v1/trips/{tripId}/place-selections/{placeId}", "200"): _success(SELECTION),
    ("post", "/api/v1/trips/{tripId}/itineraries", "201"): _success(PLAN),
    ("get", "/api/v1/trips/{tripId}/plan", "200"): _success(PLAN),
    ("patch", "/api/v1/trips/{tripId}/plan/items/order", "200"): _success(PLAN),
    ("delete", "/api/v1/trips/{tripId}/plan/items/{itemId}", "200"): _success(PLAN),
    ("post", "/api/v1/trips/{tripId}/plan/items", "200"): _success(PLAN),
    ("patch", "/api/v1/trips/{tripId}/plan/items/{itemId}/fixed", "200"): _success(PLAN),
    ("patch", "/api/v1/trips/{tripId}/plan/items/{itemId}/time", "200"): _success(PLAN),
    ("post", "/api/v1/users/me/bootstrap", "201"): _success(USER),
    ("get", "/api/v1/users/me", "200"): _success(USER),
    ("patch", "/api/v1/users/me", "200"): _success(USER),
    ("patch", "/api/v1/users/me/support-team", "200"): _success(USER),
    ("post", "/api/v1/users/me/term-agreements", "200"): _success({"agreements": [{"termCode": "TERMS_OF_SERVICE", "version": "1.0", "agreed": True, "agreedAt": "2026-08-15T10:00:00+09:00"}]}),
    ("get", "/api/v1/tour/nearby", "200"): _list([PLACE]),
    ("get", "/api/v1/tour/places/{placeId}", "200"): _success(PLACE),
    ("get", "/api/v1/tour/search", "200"): _list([PLACE]),
    ("get", "/api/v1/tour/classifications", "200"): _list([{
        "lclsSystem1": "FD", "lclsSystem1Name": "음식",
        "lclsSystem2": "FD02", "lclsSystem2Name": "외국식",
        "lclsSystem3": "FD020200", "lclsSystem3Name": "일식",
    }]),
    ("get", "/api/v1/tour/player-picks", "200"): _list([{
        "playerPickId": "player_pick_001", "stadiumId": "gocheok",
        "playerName": "홍길동", "place": PLACE,
        "recommendationNote": "선수 부모님이 운영하는 가게",
    }]),
    ("get", "/api/v1/tour/filter-options", "200"): _list([{
        "filterId": "FISHING", "label": "낚시", "group": "액티비티",
        "classificationCodes": ["LS020500", "LS020600"],
    }]),
}

PARAMETER_DOCS = {
    "attendanceLogId": ("직관 로그 문서 ID", "log_001"),
    "tripId": ("여행 문서 ID", "trip_001"), "gameId": ("경기 문서 ID", GAME["gameId"]),
    "collectionId": ("개인 찜 컬렉션 ID", "collection_001"),
    "placeId": ("내부 장소 ID. TourAPI 장소는 tour_{contentId} 형식", PLACE["placeId"]),
    "itemId": (
        "저장된 일정 안에서 항목을 식별하는 불투명 ID. 날짜·순서 등 "
        "문자열 형식을 해석하지 말고 응답 값을 그대로 사용",
        "item_1_1",
    ),
    "Idempotency-Key": ("여행 중복 생성을 방지하는 요청별 고유 문자열", "trip-create-20260816-001"),
    "date": ("한국시간 기준 경기 날짜(YYYY-MM-DD)", "2026-08-16"),
    "teamId": ("홈팀 또는 원정팀 구단 ID", "lg"),
    "stadiumId": ("구장 ID", "gocheok"), "status": ("경기 상태", "SCHEDULED"),
    "longitude": ("검색 기준 경도(WGS84)", 127.0719),
    "latitude": ("검색 기준 위도(WGS84)", 37.5122),
    "radius": ("검색 반경(미터, 최대 20000)", 2000),
    "category": ("내부 장소 카테고리 필터", "RESTAURANT"),
    "pageSize": ("한 페이지에서 반환할 최대 장소 수", 20),
    "pageToken": ("이전 응답의 nextPageToken. 첫 요청에서는 생략", "2"),
    "keyword": ("검색할 장소명 또는 키워드", "잠실 맛집"),
    "lclsSystem1": ("TourAPI 신분류 대분류 코드", "FD"),
    "lclsSystem2": ("TourAPI 신분류 중분류 코드", "FD02"),
    "lclsSystem3": ("TourAPI 신분류 소분류 코드", "FD020200"),
    "filterId": (
        "프론트 통합 필터 ID. category 및 lclsSystem 코드와 함께 사용하지 않음",
        "CAFE",
    ),
    "playerName": ("선수 이름 선택 필터. 생략하면 구장의 전체 선수 추천", "홍길동"),
}

OPERATION_PARAMETER_DOCS = {
    ("get", "/api/v1/accommodations/search", "keyword"): (
        "검색할 숙소 이름 또는 숙박 관련 키워드",
        "잠실 호텔",
    ),
    ("get", "/api/v1/accommodations/search", "pageSize"): (
        "한 페이지에서 반환할 최대 숙소 수(기본값·최대값 15)",
        15,
    ),
}


def apply_normal_examples(schema: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(schema)
    for path, path_item in result.get("paths", {}).items():
        for method, operation in path_item.items():
            method_key = method.lower()
            if method_key not in {"get", "post", "put", "patch", "delete"}:
                continue
            request_example = REQUEST_EXAMPLES.get((method_key, path))
            if request_example is not None:
                media = operation["requestBody"]["content"].get("application/json")
                if media is not None:
                    media["examples"] = {"normal": {"summary": "정상 요청", "value": request_example}}
            for status_code, response in operation.get("responses", {}).items():
                example = SUCCESS_EXAMPLES.get((method_key, path, status_code))
                if example is not None:
                    media = response.setdefault("content", {}).setdefault("application/json", {})
                    media["examples"] = {"normal": {"summary": "정상 응답", "value": example}}
            for parameter in operation.get("parameters", []):
                parameter_name = parameter.get("name")
                doc = OPERATION_PARAMETER_DOCS.get(
                    (method_key, path, parameter_name)
                ) or PARAMETER_DOCS.get(parameter_name)
                if doc is not None:
                    parameter["description"], parameter["example"] = doc
    return result


def install_normal_openapi_examples(app: FastAPI) -> None:
    original_openapi = app.openapi

    def custom_openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            app.openapi_schema = apply_normal_examples(original_openapi())
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]

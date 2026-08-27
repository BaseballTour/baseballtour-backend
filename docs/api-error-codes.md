# API 예외 응답 코드 명세

모든 오류는 아래 공통 형식을 사용한다.

```json
{
  "success": false,
  "error": {
    "code": "TRIP_NOT_FOUND",
    "message": "여행 정보를 찾을 수 없습니다.",
    "details": []
  }
}
```

프론트엔드는 `message` 문자열이 아니라 `error.code`로 분기한다.

## 공통·인증

| HTTP | code | 의미 |
| --- | --- | --- |
| 422 | `VALIDATION_ERROR` | 요청 본문·쿼리·경로 값 검증 실패 |
| 401 | `AUTH_TOKEN_MISSING` | Authorization Bearer 토큰 누락 |
| 401 | `AUTH_TOKEN_INVALID` | 토큰 형식·서명·대상 프로젝트 오류 |
| 401 | `AUTH_TOKEN_EXPIRED` | ID Token 만료 |
| 401 | `AUTH_TOKEN_REVOKED` | 폐기된 ID Token |
| 403 | `USER_DELETED` | 삭제 처리된 사용자 |
| 404 | `USER_NOT_FOUND` | 사용자 문서 없음 |
| 500 | `INTERNAL_SERVER_ERROR` | 처리되지 않은 서버 오류 |

## 외부 장소 API

| HTTP | code | 의미 |
| --- | --- | --- |
| 400 | `INVALID_PAGE_TOKEN` | 페이지 토큰 형식 오류 |
| 400 | `INVALID_PLACE_ID` | `tour_{contentId}` 형식 오류 |
| 429 | `EXTERNAL_API_RATE_LIMITED` | TourAPI 호출 한도 초과 |
| 502 | `EXTERNAL_API_INVALID_RESPONSE` | 외부 응답 구조·JSON 오류 |
| 502 | `TOUR_API_FAILED` | TourAPI 업무 오류 |
| 503 | `EXTERNAL_API_TIMEOUT` | 외부 API 제한시간 초과 |
| 503 | `EXTERNAL_API_UNAVAILABLE` | 키 누락·연결 실패·일시 장애 |

## 여행·일정

| HTTP | code | 의미 |
| --- | --- | --- |
| 400 | `TRIP_TIME_INVALID` | 여행 시작·종료시각 오류 |
| 400 | `GAME_OUTSIDE_TRIP_PERIOD` | 경기가 여행 기간 밖에 있음 |
| 400 | `ITINERARY_INPUT_INVALID` | 일정 생성 입력 오류 |
| 400 | `ITINERARY_EDIT_INVALID` | 순서 변경 등 엄격 편집 규칙 위반 |
| 400 | `ITINERARY_ANCHOR_NOT_EDITABLE` | PLACE가 아닌 Anchor Item의 시간 변경 시도 |
| 400 | `ITINERARY_ITEM_DATE_MISMATCH` | 장소 추가 날짜와 시작시각 날짜 불일치 |
| 403 | `TRIP_ACCESS_DENIED` | 다른 사용자의 여행 접근 |
| 404 | `TRIP_NOT_FOUND` | 여행 없음 |
| 404 | `ITINERARY_PLAN_NOT_FOUND` | 활성 일정 없음 |
| 404 | `ITINERARY_DAY_NOT_FOUND` | 수정 대상 날짜 없음 |
| 404 | `ITINERARY_ITEM_NOT_FOUND` | 수정 대상 Item 없음 |
| 404 | `ITINERARY_PLACE_NOT_FOUND` | 추가할 TourAPI 장소 없음 |
| 409 | `TRIP_GENERATION_IN_PROGRESS` | 일정 생성 중 중복 작업 |
| 409 | `ITINERARY_PLACE_ALREADY_EXISTS` | 같은 날짜에 장소 중복 추가 |
| 409 | `FIXED_ITEM_TIME_CONFLICT` | 재생성 시 고정 장소가 다른 필수·사용자 항목과 겹침. `details.fixedItem`, `details.conflictingItem`으로 충돌 항목 확인 |
| 409 | `FIXED_ITEM_OUTSIDE_TRIP` | 고정 장소의 날짜가 변경된 여행 기간 밖에 있음. `details.conflictingItem`으로 항목 확인 |

## 찜 컬렉션·여행 후보

| HTTP | code | 의미 |
| --- | --- | --- |
| 404 | `FAVORITE_COLLECTION_NOT_FOUND` | 컬렉션 없음 |
| 404 | `FAVORITE_COLLECTION_ITEM_NOT_FOUND` | 찜 장소 없음 |
| 422 | `INVALID_FAVORITE_PLACE` | TourAPI 장소가 아닌 ID |
| 404 | `PLACE_SELECTION_NOT_FOUND` | 여행 후보 장소 없음 |
| 409 | `PLACE_SELECTION_ALREADY_EXISTS` | 여행 후보 중복 |

Swagger의 각 API에서 **Responses**를 펼치면 상태 코드별 실제 JSON 예시를 확인할 수 있다. 같은 HTTP 상태에 여러 `error.code`가 있으면 Example 드롭다운에서 상황별 예시를 선택한다. 이 문서는 전체 코드 의미를 확인하는 기준으로 함께 사용한다.

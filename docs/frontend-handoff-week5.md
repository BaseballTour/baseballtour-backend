# 프론트엔드 전달 사항 — 검색·선수추천·일정

## 관광 장소 검색

```http
GET /api/v1/tour/search?keyword=잠실&filterId=KOREAN&pageSize=20
```

- 사용자가 입력할 때마다 호출하지 않고 마지막 입력 후 300~500ms 뒤 호출한다.
- 같은 검색어·필터·페이지 결과는 백엔드가 30분 동안 캐시한다.
- 동시에 들어온 동일 검색은 백엔드가 한 번의 TourAPI 호출로 합친다.
- HTTP 429와 `EXTERNAL_API_RATE_LIMITED`가 오면 자동 연속 재시도하지 않는다.

권장 안내 문구:

```text
관광지 검색 요청이 많아 잠시 사용할 수 없습니다.
잠시 후 다시 시도해 주세요.
```

빈 결과는 오류가 아니며 다음처럼 반환한다.

```json
{
  "success": true,
  "data": [],
  "meta": {"count": 0, "nextPageToken": null}
}
```

## 선수 추천 장소

```http
GET /api/v1/tour/player-picks?stadiumId=sajik
GET /api/v1/tour/player-picks?stadiumId=sajik&playerName=정보근
```

현재 Firestore에는 184건이 저장되어 있다. 장소 정보는 저장 시점 스냅샷을
반환하므로 TourAPI 장애 중에도 목록을 표시할 수 있다.

```json
{
  "playerPickId": "player_pick_...",
  "stadiumId": "sajik",
  "playerName": "정보근",
  "place": {
    "placeId": "player_place_...",
    "name": "화로우",
    "address": "부산광역시 강서구 명지국제6로232번길 8 1층"
  },
  "recommendationNote": "선수 부모님이 운영하는 가게"
}
```

- `recommendationNote`가 있으면 장소 카드에 부가 설명으로 표시한다.
- `thumbnailUrl=null`이면 공통 placeholder 이미지를 표시한다.
- 선수 추천 장소는 일반 TourAPI 자동 추천 후보가 아니라 별도 큐레이션이다.

## 일정 결과

- `travelTimeSource=ESTIMATED`이면 `예상 이동시간`으로 표시한다.
- `businessHoursStatus=MISSING` 또는 `UNPARSABLE`이면 운영 가능 여부를
  단정하지 않고 `운영시간 확인 필요`로 표시한다.
- `recommendationSummary`는 개발·운영 진단용이며 사용자용 카피로 직접
  노출하지 않는다.
- 고정한 Item은 재생성 후 유지하고, 고정하지 않은 자동 추천은 교체될 수 있다.
- 편집 충돌 오류의 `details`에 포함된 `itemId`를 이용해 충돌 항목을 강조한다.

## 장애 처리

| HTTP | code | 프론트 처리 |
| ---: | --- | --- |
| 429 | `EXTERNAL_API_RATE_LIMITED` | 연속 재시도 중단, 잠시 후 안내 |
| 502 | `EXTERNAL_API_INVALID_RESPONSE` | 일시 오류 안내 |
| 503 | `EXTERNAL_API_TIMEOUT` | 재시도 버튼 제공 |
| 503 | `EXTERNAL_API_UNAVAILABLE` | 외부 서비스 장애 안내 |

백엔드는 timeout 시 `details.timeoutType`으로 연결 실패와 응답 지연을
구분하지만, 이 값은 운영 진단용이므로 일반 사용자에게 그대로 표시하지 않는다.

# API 명세서 v1.0 초안

공통 prefix: `/api/v1`

## 구현 완료

| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/games` | 날짜·구단·구장·상태별 경기 목록 |
| GET | `/games/{gameId}` | 경기 상세 |
| POST | `/trips` | 여행 기본정보 생성 |
| GET | `/trips` | 내 여행 목록 |
| GET | `/trips/{tripId}` | 여행 상세 |
| PATCH | `/trips/{tripId}` | 여행 기본정보 수정 |
| DELETE | `/trips/{tripId}` | 여행 삭제 |
| GET | `/tour/nearby` | TourAPI 위치 기반 장소 조회 |
| GET | `/tour/places/{placeId}` | 내부 장소 ID 기반 TourAPI 상세·소개·이미지 통합 조회 |
| GET | `/accommodations/search` | Kakao 숙박업소 검색 |
| GET | `/accommodations/reverse-geocode` | 지도 좌표를 숙소 Anchor 후보로 변환 |

### TourAPI 상세 조회

```http
GET /api/v1/tour/places/tour_1603175
```

`placeId`는 주변 장소 조회 응답의 값을 그대로 사용한다. 백엔드가 `tour_` 접두사를 제거해 TourAPI 원본 `contentId`를 얻고, 공통정보에서 `contentTypeId`를 확인한다. 성공 응답의 `data`는 내부 `Place` 모델이며 이미지·영업시간이 없으면 `null`이다.

## 연결 예정

```http
POST /api/v1/trips/{tripId}/itineraries
```

백엔드가 Trip·Game·Stadium·선택 Place를 `TripInput`으로 조합하고 알고리즘을 호출한다. 성공 시 ACTIVE Plan 저장과 `activePlanId` 변경을 transaction으로 처리한다.

알고리즘 입력·응답 JSON 예시는 `samples/algorithm`을 사용한다. 오류 응답은 공통 `success=false`, `error.code`, `error.message`, `error.details` 구조를 따른다.

### 여행 후보 장소 계약

```json
{
  "selectedPlaces": [
    {
      "placeId": "tour_123456",
      "isRequired": true
    }
  ]
}
```

- 찜 컬렉션에서 불러오기, 주변 추천에서 선택, 홈·지도에서 직접 추가한 장소는
  모두 동일한 사용자 선택 후보다.
- 유입 경로는 알고리즘 요청과 응답에 포함하지 않는다. 분석이 필요하면 별도
  이벤트 로그로 기록한다.
- `isRequired=true`는 일정에 반드시 포함하도록 최우선으로 시도한다.
- 필수 장소가 불가능하면 결과의 `hasRequiredPlaceConflict`와
  `excludedPlaces[].isRequired`로 충돌을 전달한다.
- `isFixed`는 저장 일정 Item의 재생성 정책이며 여행 후보 입력과 분리한다.

권장 후보 저장 경로:

```text
trips/{tripId}/placeCandidates/{placeId}
```

```json
{
  "placeId": "tour_123456",
  "isRequired": false,
  "createdAt": "...",
  "updatedAt": "..."
}
```

홈·지도에서 바로 추가하거나 컬렉션에서 불러와도 같은 문서를 생성한다. 문서 ID를
`placeId`로 사용하여 중복을 방지한다.

장소를 배정하지 못하면 다음 제외 사유를 사용한다.

| code | 의미 |
| --- | --- |
| `CLOSED_DAY` | 여행 기간 동안 방문 가능한 영업일이 없음 |
| `ADMISSION_DEADLINE` | 안전하게 해석된 입장·매표 마감 이후 도착 |
| `OUTSIDE_BUSINESS_HOURS` | 체류 종료가 영업 종료를 초과 |
| `ANCHOR_CONFLICT` | 방문 시 경기장 또는 출발지 필수 도착시각 위반 |
| `INSUFFICIENT_TIME` | 그 밖의 하루 시간 예산 부족 |
| `DUPLICATE_PLACE` | 같은 장소 중복 선택 |
| `INVALID_PLACE` | Place 정보를 찾지 못함 |

저장된 일정 Item에는 다음 필드를 둔다.

```json
{
  "itemId": "item_001",
  "isFixed": true
}
```

초기 정책에서 `isFixed=true`는 날짜와 순서를 보존하되 정확한 시작·종료시각은
앞뒤 이동시간에 맞춰 다시 계산한다.

### 자동 추천 결과 계약

사용자가 선택한 후보를 먼저 배정한 뒤 남는 시간에 추천 후보를 삽입한다.

```json
{
  "type": "PLACE",
  "placeId": "tour_789012",
  "isRequired": false,
  "addedBy": "ALGORITHM"
}
```

- `addedBy=USER`: 필수·일반 사용자 후보에서 생성된 Item
- `addedBy=ALGORITHM`: 빈 시간을 채우기 위해 알고리즘이 추가한 Item
- Anchor Item은 추천 출처 대상이 아니므로 `addedBy=null`이다.

결과 메타데이터:

```json
{
  "autoFillApplied": true,
  "autoRecommendedPlaceCount": 3
}
```

추천할 장소가 없거나 조건을 만족하지 못해도 일정 생성은 성공하며
`autoFillApplied=false`를 반환한다. 추천 개수 상한은 없고 추가 이동시간 30분,
삽입 후 최소 여유 30분, 영업시간·입장 마감·Anchor 제약으로 제한한다.

카테고리별 기본 체류시간은 카페 45분, 음식점 60분, 관광지·문화시설 90분,
쇼핑 60분, 액티비티·축제 120분, 기타 60분이다. 숙박은 자동 추천에서 제외한다.

### 찜 컬렉션 연결 예정

```text
GET    /users/me/favorite-collections
POST   /users/me/favorite-collections
PATCH  /users/me/favorite-collections/{collectionId}
DELETE /users/me/favorite-collections/{collectionId}
PUT    /users/me/favorite-collections/{collectionId}/items/{placeId}
DELETE /users/me/favorite-collections/{collectionId}/items/{placeId}
```

구단별 컬렉션은 제공하지 않고 개인 찜 컬렉션만 사용한다. 일정에 컬렉션을
불러올 때는 선택한 경기·경기장의 지역과 일치하는 TourAPI 장소만 여행 후보로
자동 포함한다. 컬렉션 Item은 `placeId`만 참조한다. Kakao 검색 결과는 독립
장소로 저장하지 않고 TourAPI 장소의 부족한 기본 정보 보충에만 사용한다.

### 일정 이동 구간 계약

각 일정 Item은 이전 Item에서 이동한 시간과 수단·출처를 포함한다.

```json
{
  "travelMinutesFromPrevious": 8,
  "travelMode": "WALK",
  "travelTimeSource": "ESTIMATED"
}
```

- `travelMode`: `WALK`, `TRANSIT`
- `travelTimeSource`: `KAKAO`, `ODSAY`, `ESTIMATED`, `FAKE`
- 신규 일정은 카카오 실제 도보·대중교통 시간 중 더 짧은 값을 사용한다.
- `ODSAY`는 기존 저장 일정과의 하위 호환을 위해 유지한다.
- `FAKE`는 테스트와 Mock 전용이다.
- 이동이 없는 첫 Item은 `travelMode`, `travelTimeSource`가 `null`일 수 있다.

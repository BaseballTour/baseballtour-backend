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
- `travelTimeSource`: `ODSAY`, `ESTIMATED`, `FAKE`
- 도보 예상시간과 ODsay 대중교통 최단시간 중 더 짧은 값을 사용한다.
- `FAKE`는 테스트와 Mock 전용이다.
- 이동이 없는 첫 Item은 `travelMode`, `travelTimeSource`가 `null`일 수 있다.

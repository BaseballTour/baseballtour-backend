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
| GET | `/tour/places/{contentId}` | TourAPI 장소 상세·소개·이미지 통합 조회 |

### TourAPI 상세 조회

```http
GET /api/v1/tour/places/123456
```

성공 응답의 `data`는 내부 `Place` 모델이며 이미지·영업시간이 없으면 `null`이다.

## 연결 예정

```http
POST /api/v1/trips/{tripId}/itineraries
```

백엔드가 Trip·Game·Stadium·선택 Place를 `TripInput`으로 조합하고 알고리즘을 호출한다. 성공 시 ACTIVE Plan 저장과 `activePlanId` 변경을 transaction으로 처리한다.

알고리즘 입력·응답 JSON 예시는 `samples/algorithm`을 사용한다. 오류 응답은 공통 `success=false`, `error.code`, `error.message`, `error.details` 구조를 따른다.

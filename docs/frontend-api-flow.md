# 프론트엔드 API 연동 흐름

정확한 필드 형식과 정상·오류 JSON은 실행 중인 서버의 `/docs`를 기준으로 한다. 이 문서는 화면에서 API를 호출하는 순서와 정책만 설명한다.

## 기본 흐름

1. Firebase Authentication에서 ID Token을 발급받는다.
2. `Authorization: Bearer {ID_TOKEN}`으로 사용자 프로필을 조회하거나 생성한다.
3. 경기 목록에서 `gameId`를 선택한다.
4. TourAPI 주변 조회 또는 키워드 검색에서 `placeId`를 확보한다.
5. 장소를 개인 컬렉션에 찜하거나 여행 후보에 바로 추가한다.
6. 여행을 만들고 후보 장소의 `isRequired`를 확정한다.
7. 일정을 생성한 뒤 상세 조회·순서 변경·시간 변경·고정을 수행한다.

## 주요 호출 순서

```text
GET  /api/v1/games
GET  /api/v1/tour/nearby 또는 /api/v1/tour/search
POST /api/v1/trips
POST /api/v1/trips/{tripId}/place-selections
POST /api/v1/trips/{tripId}/itineraries
GET  /api/v1/trips/{tripId}/plan
```

개인 컬렉션을 사용하는 경우에는 `POST /trips/{tripId}/place-selections/import`로 해당 경기 지역의 장소만 여행 후보에 복사한다.

## 화면 처리 기준

- 날짜·시간은 `+09:00`이 포함된 ISO 8601 문자열을 사용한다.
- 오류 화면 분기는 HTTP 상태가 아니라 `error.code`를 기준으로 한다.
- `thumbnailUrl=null`이면 공통 placeholder 이미지를 표시한다.
- 운영시간이 없으면 `운영시간 확인 필요`로 표시한다.
- 일정 Item의 `type`과 `category`를 구분한다.
- 수동 장소 추가·시간 변경은 사용자 결정을 보존하며 이동시간만 다시 계산한다.
- `204 No Content` 응답은 JSON 본문이 없다.

## 테스트 데이터

- 알고리즘 내부 입력·출력: `samples/algorithm/`
- TourAPI 원본 응답: `samples/tour_api/`
- 경기·구장 Firestore Seed: `samples/firestore/`

Mock 파일은 서버 없이 화면을 개발할 때 사용한다. 실제 API 계약과 필드가 충돌하면 Swagger를 우선하고 Mock 파일을 갱신한다.

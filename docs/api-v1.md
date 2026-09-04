# API 명세서 v1.1

공통 prefix: `/api/v1`
단, 루트 상태 확인 API `/`는 prefix를 사용하지 않는다.

## API 목록

| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/` | API 기본 정보 |
| GET | `/accommodations/reverse-geocode` | 지도에서 숙소 검색 |
| GET | `/accommodations/search` | Kakao 숙소 검색 |
| GET | `/attendance-logs` | 내 직관 로그 목록 조회 |
| POST | `/attendance-logs` | 직관 로그 초안 생성 |
| GET | `/attendance-logs/{attendanceLogId}` | 직관 로그 상세 조회 |
| PATCH | `/attendance-logs/{attendanceLogId}` | 직관 로그 수정 |
| DELETE | `/attendance-logs/{attendanceLogId}` | 직관 로그 삭제 |
| PATCH | `/attendance-logs/{attendanceLogId}/entries/{entryId}` | 직관 로그 Entry 수정 |
| DELETE | `/attendance-logs/{attendanceLogId}/entries/{entryId}` | 직관 로그 Entry 삭제 |
| DELETE | `/attendance-logs/{attendanceLogId}/entries/{entryId}/media/{mediaId}` | 직관 로그 미디어 삭제 |
| GET | `/attendance-logs/{attendanceLogId}/itinerary` | 직관 로그 일정 조회 |
| GET | `/games` | KBO 경기 목록 조회 |
| GET | `/games/{gameId}` | KBO 경기 상세 조회 |
| GET | `/health` | 서버 상태 확인 |
| POST | `/media/complete` | 미디어 업로드 완료 |
| POST | `/media/upload-urls` | 미디어 업로드 URL 발급 |
| GET | `/teams` | KBO 구단 목록 조회 |
| GET | `/terms` | 활성 약관 목록 조회 |
| GET | `/tour/classifications` | TourAPI 신분류 코드 목록 조회 |
| GET | `/tour/nearby` | Read Nearby Places |
| GET | `/tour/places/{placeId}` | Read Place Detail |
| GET | `/tour/player-picks` | 구장·선수별 추천 장소 조회 |
| GET | `/tour/search` | 관광 장소 키워드 검색 |
| GET | `/trips` | 내 여행 목록 조회 |
| POST | `/trips` | 여행 생성 |
| GET | `/trips/{tripId}` | 여행 상세 조회 |
| PATCH | `/trips/{tripId}` | 여행 기본정보 수정 |
| DELETE | `/trips/{tripId}` | 여행 삭제 |
| POST | `/trips/{tripId}/itineraries` | 여행 일정 생성 및 저장 |
| GET | `/trips/{tripId}/place-selections` | 여행 장소 선택 목록 조회 |
| POST | `/trips/{tripId}/place-selections` | 여행 장소 선택 추가 |
| POST | `/trips/{tripId}/place-selections/import` | 개인 찜 컬렉션에서 여행 후보 불러오기 |
| PATCH | `/trips/{tripId}/place-selections/{placeId}` | 여행 후보 필수 방문 여부 변경 |
| DELETE | `/trips/{tripId}/place-selections/{placeId}` | 여행 장소 선택 삭제 |
| GET | `/trips/{tripId}/plan` | 여행 일정 상세 조회 |
| DELETE | `/trips/{tripId}/plan` | 여행 일정 삭제 |
| POST | `/trips/{tripId}/plan/items` | 여행 일정 장소 추가 |
| PATCH | `/trips/{tripId}/plan/items/order` | 여행 일정 장소 순서 변경 |
| DELETE | `/trips/{tripId}/plan/items/{itemId}` | 여행 일정 장소 삭제 |
| PATCH | `/trips/{tripId}/plan/items/{itemId}/fixed` | 여행 일정 장소 고정 여부 변경 |
| PATCH | `/trips/{tripId}/plan/items/{itemId}/time` | 여행 일정 장소 시작시간 변경 |
| GET | `/trips/{tripId}/recommendation-candidates` | 일정 생성 전 추천 후보 조회 |
| GET | `/users/me` | 내 사용자 정보 조회 |
| PATCH | `/users/me` | 내 사용자 정보 수정 |
| DELETE | `/users/me` | 회원탈퇴 |
| POST | `/users/me/bootstrap` | 최초 사용자 프로필 생성 |
| GET | `/users/me/favorite-collections` | 개인 찜 컬렉션 목록 조회 |
| POST | `/users/me/favorite-collections` | 개인 찜 컬렉션 생성 |
| GET | `/users/me/favorite-collections/{collectionId}` | 개인 찜 컬렉션 장소 목록 조회 |
| PATCH | `/users/me/favorite-collections/{collectionId}` | 개인 찜 컬렉션 이름 변경 |
| DELETE | `/users/me/favorite-collections/{collectionId}` | 개인 찜 컬렉션 삭제 |
| PUT | `/users/me/favorite-collections/{collectionId}/items/{placeId}` | 찜 장소 저장 |
| DELETE | `/users/me/favorite-collections/{collectionId}/items/{placeId}` | 찜 장소 삭제 |
| POST | `/users/me/term-agreements` | 약관 동의 저장 |

## v1.1 주요 계약 변경

### 사용자 프로필 통합 수정

`PATCH /api/v1/users/me`에서 사용자 프로필을 통합 수정한다.
닉네임 수정도 별도 API 없이 이 API를 사용한다.

수정 가능한 필드는 다음과 같다.

- `nickname`: 닉네임
- `name`: 사용자 이름
- `phoneNumber`: 휴대폰 번호
- `profileImageUrl`: 프로필 이미지 URL
- `supportTeamId`: 응원팀 ID

`nickname`, `supportTeamId`는 명시적으로 `null`을 전달할 수 없다.
`name`, `phoneNumber`, `profileImageUrl`은 `null`을 전달하면 해당 값을
삭제한다.

프로필 이미지는 신규 구현에서는 미디어 업로드 API를 사용하는 것을 기본으로 한다.
기존 `profileImageUrl` 직접 수정 방식은 호환성을 위해 유지한다.
`profileImageUrl`을 명시적으로 변경하거나 `null`로 삭제하면 기존
`profileImageStoragePath` 연결도 해제하여 이전 Storage 이미지가 다시
fallback되지 않도록 한다.

Storage에 저장된 프로필 이미지가 있는 경우 사용자 응답의
`profileImageUrl`에는 임시 signed GET URL을 반환한다.
Storage 내부 경로는 사용자 응답에 노출하지 않으며, signed URL은 영구 URL로
저장하거나 캐시하지 않는다.

### 미디어 업로드 계약

미디어 업로드는 다음 3단계로 수행한다.

1. `POST /api/v1/media/upload-urls`로 V4 signed PUT URL을 발급받는다.
2. 클라이언트가 반환된 URL에 지정된 `Content-Type`으로 파일을 직접 PUT한다.
3. 업로드가 끝나면 `POST /api/v1/media/complete`를 호출해 실제 Storage
   객체 검증과 서비스 데이터 연결을 완료한다.

미디어 목적은 다음 두 가지다.

- `PROFILE_IMAGE`: 사용자 프로필 이미지
- `ATTENDANCE_LOG`: 직관 로그 이미지 또는 동영상

지원 형식과 최대 크기는 다음과 같다.

| 용도 | 형식 | 최대 크기 |
| --- | --- | ---: |
| 프로필 이미지 | JPEG, PNG, WebP, HEIC, HEIF | 10 MB |
| 직관 로그 이미지 | JPEG, PNG, WebP, HEIC, HEIF | 15 MB |
| 직관 로그 동영상 | MP4, QuickTime, WebM | 200 MB |

업로드 signed URL은 15분 동안 유효하고 조회 signed URL은 1시간 동안
유효하다.

`complete`에서는 클라이언트가 처음 전달한 파일 정보만 신뢰하지 않고 실제
Storage 객체를 다시 조회해 다음 항목을 검증한다.

- 사용자 소유 Storage 경로인지 여부
- 실제 `Content-Type`
- 실제 파일 크기
- Storage 경로 확장자
- 직관 로그 및 Entry 소유권

실제 업로드 객체가 형식 또는 크기 정책을 위반하거나 불완전한 경우 해당
Storage 객체를 best-effort로 삭제하여 orphan 파일이 남지 않도록 한다.

프로필 이미지 업로드가 완료되면 `profileImageStoragePath`를 기준 데이터로
사용하고 기존 외부 `profileImageUrl` 값은 제거한다. 이전 Storage 프로필
이미지가 있으면 새 이미지 연결 성공 후 이전 객체를 정리한다.

### 직관 로그 공개 범위와 소유권

직관 로그의 `visibility`는 다음 값을 사용한다.

- `PRIVATE`: 비공개
- `PUBLIC`: 공개

새 직관 로그 초안의 기본값은 `PRIVATE`이다.
`visibility` 필드가 없는 기존 Firestore 문서도 `PRIVATE`로 취급한다.

조회 권한은 다음과 같다.

- `GET /api/v1/attendance-logs`: 자신의 직관 로그 목록만 조회
- `GET /api/v1/attendance-logs/{attendanceLogId}`:
  소유자는 항상 조회할 수 있고, 다른 인증 사용자는 `PUBLIC` 로그만 조회 가능
- 비로그인 공개 조회 및 공개 로그 feed API는 제공하지 않는다.

수정 권한은 공개 여부와 관계없이 소유자에게만 있다.

- 직관 로그 수정·삭제
- Entry 수정·삭제
- 미디어 삭제

`GET /api/v1/attendance-logs/{attendanceLogId}/itinerary`도
직관 로그가 `PUBLIC`이어도 소유자 전용이다. 공개 로그를 조회한 다른 사용자가
연결된 여행 일정 전체를 조회할 수는 없다.

`PATCH /api/v1/attendance-logs/{attendanceLogId}`에서
`visibility`를 변경할 수 있으며 명시적인 `null`은 허용하지 않는다.

### 약관 마스터와 동의

활성 약관은 `GET /api/v1/terms`로 조회하고 사용자 동의는
`POST /api/v1/users/me/term-agreements`로 저장한다.

현재 개발·staging seed의 약관 종류는 다음과 같다.

- `TERMS_OF_SERVICE`: 필수
- `PRIVACY_POLICY`: 필수
- `LOCATION_BASED_SERVICE`: 필수
- `MARKETING`: 선택

현재 seed 버전은 `1.0`, 시행일은 `2026-08-01` KST 기준이다.
개발·staging의 약관 본문은 출시 전 교체해야 하는 placeholder이며,
placeholder seed는 production 환경에서 실행하지 않는다.

### 팀 로고 응답 계약

클라이언트에는 기존과 동일하게 `logoUrl`만 제공하며 내부
`logoStoragePath`는 노출하지 않는다.

팀 문서에 `logoStoragePath`가 있으면 Firebase Storage signed GET URL을
`logoUrl`로 반환하고, 아직 Storage 로고가 없는 기존 데이터는 legacy
`logoUrl`을 fallback으로 사용할 수 있다.

사용자 응답의 `supportTeam.logoUrl`과 경기 응답의 홈·원정팀 `logoUrl`도
동일한 규칙을 사용한다.

### 여행 subtitle 계약

여행 생성·수정 시 `subtitle`을 직접 지정할 수 있다.

응답의 `subtitle`은 항상 문자열이며 직접 지정한 값이 없으면 여행 기간으로
자동 생성한다.

- 당일 여행: `2026.08.16`
- 여러 날 여행: `2026.08.16 ~ 2026.08.17`
- 빈 문자열은 사용자 지정 subtitle로 저장하지 않고 자동 생성 규칙을 사용한다.

### 일정 PLACE 표시 계약

저장 일정의 `PLACE` Item은 장소 카드 표시를 위해 다음 정보를 제공한다.

- `thumbnailUrl`: 장소 썸네일
- `shortDescription`: 한 줄 표시용 장소 소개
- `overview`: 원본 장소 소개

`shortDescription`은 `overview`의 줄바꿈과 연속 공백을 한 줄로 정규화한 값이며,
원본 `overview`를 대체하지 않는다. 소개가 없으면 `null`일 수 있다.

### 직관 로그 일정 조회

`GET /api/v1/attendance-logs/{attendanceLogId}/itinerary`는 직관 로그와
연결된 당시 일정 Plan을 읽기 전용으로 반환한다.

직관 로그가 생성된 뒤 여행 일정이 다시 생성되어 기존 Plan이 `ARCHIVED` 상태가
되어도 로그에 저장된 `planId`를 기준으로 당시 Plan을 조회한다. 이 API는 일정
수정 또는 재생성을 수행하지 않는다.

주요 오류 코드는 다음과 같다.

| code | 의미 |
| --- | --- |
| `ATTENDANCE_LOG_NOT_FOUND` | 직관 로그 없음 |
| `ATTENDANCE_LOG_ACCESS_DENIED` | 다른 사용자의 직관 로그 |
| `ITINERARY_PLAN_NOT_FOUND` | 연결된 일정 Plan 없음 |
| `ATTENDANCE_LOG_PLAN_MISMATCH` | 로그와 Plan의 사용자 또는 여행 정보 불일치 |

### TourAPI 상세 조회

```http
GET /api/v1/tour/places/tour_1603175
```

`placeId`는 주변 장소 조회 응답의 값을 그대로 사용한다. 백엔드가 `tour_` 접두사를 제거해 TourAPI 원본 `contentId`를 얻고, 공통정보에서 `contentTypeId`를 확인한다. 성공 응답의 `data`는 내부 `Place` 모델이며 이미지·영업시간이 없으면 `null`이다.

### TourAPI 검색 호출 보호

`GET /api/v1/tour/search`의 동일 검색어·필터·페이지 성공 결과는 서버 인스턴스
안에서 30분 동안 캐시한다. 같은 요청이 동시에 들어오면 한 번의 외부 호출로
합친다. TourAPI 일일 호출 한도 초과가 발생한 동일 조건은 60초 동안 외부에
다시 요청하지 않고 `EXTERNAL_API_RATE_LIMITED`를 반환한다.

### 선수 추천 장소

```http
GET /api/v1/tour/player-picks?stadiumId=sajik&playerName=정보근
```

`stadiumId`는 필수이고 `playerName`은 선택 필터다. 각 결과는
`playerPickId`, `stadiumId`, `playerName`, `place`, `recommendationNote`를
포함한다. `recommendationNote`는 부모님 운영 또는 선수단 공통 추천 같은
관리자 설명이며 없으면 `null`이다. 저장된 `place` 스냅샷을 우선 사용하므로
TourAPI가 일시적으로 실패해도 큐레이션 목록을 반환할 수 있다.

### 숙소를 포함한 여행 생성

`POST /api/v1/trips`는 `gameId`, `tripStartAt`, `tripEndAt`, `arrivalPoint`,
`departurePoint`, `accommodation`을 한 요청으로 받는다. `tripStartAt`은 도착역
도착 일시, `tripEndAt`은 출발역 출발 일시로 사용한다. 경기 시작시각과 구장 정보는
프론트가 중복 전송하지 않고 백엔드가 `gameId`로 조회한다. 숙소는 카카오 검색 또는
지도 선택 결과를 사용하며 체크인·체크아웃 시각은 받지 않는다.

숙소 검색 응답은 `accommodation_kakao_{Kakao 장소 ID}`, 지도 선택 응답은
`accommodation_map_{hash}` 형식의 `accommodationId`를 제공한다. 프론트는 이 ID와
이름·주소·좌표를 여행 요청에 전달하며 검색 응답의 `kakaoPlaceId`는 다시 보내지
않는다. 숙소 전용 DB가
아직 없으므로 ID만으로 숙소를 복원하지 않고 여행 문서에 선택 당시 스냅샷을 함께
저장한다. 좌표는 소수점 6자리로 정규화하며, 잘못된 ID는 HTTP 422
`ACCOMMODATION_INVALID`로 응답한다.

일정 생성 중 추천 장소 수집이 30초 제한을 넘으면 추천 0건의 성공 결과를 저장하지
않고 HTTP 503 `RECOMMENDATION_TIMEOUT`을 반환한다.

## 일정 생성 및 편집 계약

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

### 찜 컬렉션 계약

개인 찜 컬렉션은 다음 API로 관리한다.

- `GET /users/me/favorite-collections`
- `POST /users/me/favorite-collections`
- `GET /users/me/favorite-collections/{collectionId}`
- `PATCH /users/me/favorite-collections/{collectionId}`
- `DELETE /users/me/favorite-collections/{collectionId}`
- `PUT /users/me/favorite-collections/{collectionId}/items/{placeId}`
- `DELETE /users/me/favorite-collections/{collectionId}/items/{placeId}`

`GET /users/me/favorite-collections/{collectionId}`는 컬렉션 안의 장소를
`Place` 목록으로 반환한다.

컬렉션의 `thumbnailUrl`은 현재 남아 있는 장소 중 가장 먼저 추가된 장소의
썸네일을 사용한다. 해당 장소를 삭제하면 다음으로 오래된 장소가 대표 썸네일이
된다.

컬렉션에 장소를 저장할 때 장소 스냅샷을 함께 보관한다. 조회 시 저장된 스냅샷을
우선 사용하며 필요한 경우 TourAPI 장소 정보를 다시 조회해 보완한다.

TourAPI 원본 응답은 같은 Cloud Run 인스턴스의 메모리 캐시와
`tourApiResponseCache` Firestore 공유 캐시를 함께 사용한다. 검색 응답은 30분,
상세 응답은 12시간 동안 재사용하며 외부 API 키는 캐시 문서에 저장하지 않는다.

일정으로 컬렉션을 불러올 때는 선택한 여행의 후보 장소 계약에 맞춰
`placeId` 기반 선택 항목으로 변환한다.

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
- 신규 이동시간 조회는 Kakao Routing만 사용한다.
- `ODSAY`는 기존 Firestore 저장 일정의 역직렬화 하위 호환을 위한 enum 값으로만 유지하며 ODsay API를 호출하지 않는다.
- `FAKE`는 테스트와 Mock 전용이다.
- 이동이 없는 첫 Item은 `travelMode`, `travelTimeSource`가 `null`일 수 있다.

<!-- attendance-archive:start -->

## 직관 로그 아카이브 API

### GET `/api/v1/attendance-logs`

로그인한 사용자의 직관 로그를 아카이브 휠 화면용으로 조회한다.

#### Query Parameters

| 이름 | 타입 | 필수 | 기본값 | 설명 |
| --- | --- | --- | --- | --- |
| `pageSize` | integer | X | `12` | 페이지 크기. 1~50 |
| `pageToken` | string | X | - | 이전 응답의 `nextPageToken` |

#### 주요 응답 필드

| 필드 | 설명 |
| --- | --- |
| `attendanceLogId` | 직관 로그 ID |
| `tripId` | 연결된 여행 ID |
| `gameId` | 경기 ID |
| `planId` | 로그 생성 시점 일정 ID |
| `logTitle` | 직관 로그 제목 |
| `summaryText` | 한 줄 직관 메모 |
| `seat` | 좌석 정보 |
| `gameStartAt` | 경기 시작 시각 |
| `stadiumName` | 경기장 이름 |
| `homeTeamName` | 홈 팀 이름 |
| `awayTeamName` | 원정 팀 이름 |
| `homeScore` | 홈 팀 점수 |
| `awayScore` | 원정 팀 점수 |
| `homeSide` | `HOME`, `AWAY`, `OTHER` |
| `result` | `WIN`, `LOSS`, `DRAW` 또는 `null` |
| `coverImageUrl` | 대표 이미지 URL 또는 `null` |
| `logStatus` | 로그 상태 |
| `visibility` | 공개 범위 |

`homeSide`와 `result`는 현재 사용자의 응원팀을 기준으로 계산한다.
응원팀이 경기에 참가하지 않으면 `homeSide=OTHER`, `result=null`이다.
경기 점수가 없는 경우에도 `result`는 `null`이다.

대표 이미지는 Entry 순서와 Media 순서를 기준으로
가장 먼저 발견되는 `IMAGE`를 사용한다.

```json
{
  "success": true,
  "data": [],
  "meta": {
    "count": 0,
    "nextPageToken": null
  }
}
```

### PATCH `/api/v1/attendance-logs/{attendanceLogId}`

`seat`를 함께 수정할 수 있으며 `null`을 전달하면 좌석 정보를 삭제한다.

```json
{
  "summaryText": "역전승 직관",
  "seat": "1루 내야 101구역 10열"
}
```

```json
{
  "seat": null
}
```

<!-- attendance-archive:end -->

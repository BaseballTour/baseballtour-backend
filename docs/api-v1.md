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
| PATCH | `/trips/{tripId}/plan/items/{itemId}/time` | 여행 일정 장소 시작시간·날짜 변경 |
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
- `birthDate`: 생년월일 (`YYYY-MM-DD`)
- `gender`: 성별 (`MALE`, `FEMALE`)
- `profileImageUrl`: 프로필 이미지 URL
- `supportTeamId`: 응원팀 ID

`nickname`, `supportTeamId`는 명시적으로 `null`을 전달할 수 없다.
`name`, `phoneNumber`, `birthDate`, `gender`, `profileImageUrl`은
`null`을 전달하면 해당 값을 삭제한다.

`birthDate`를 변경하면 기존 가입 호환 필드인 `birthYear`도 해당 연도로
자동 갱신한다. `birthDate`를 `null`로 삭제해도 기존 `birthYear` 값은
유지한다.

기존 사용자 문서에는 `birthDate`, `gender`가 없을 수 있으며 이 경우
사용자 응답에서 두 필드는 `null`로 반환한다.

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

미디어 목적은 다음 세 가지다.

- `PROFILE_IMAGE`: 사용자 프로필 이미지
- `ATTENDANCE_LOG`: 직관 로그 이미지 또는 동영상
- `TRIP_COVER_IMAGE`: 여행 커버이미지

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

### 여행 커버이미지 업로드 계약

여행 커버이미지는 기존 미디어 업로드 API를 재사용한다.
여행을 먼저 생성한 뒤 반환된 `tripId`로 업로드한다.

1. `POST /api/v1/media/upload-urls`에 `purpose: "TRIP_COVER_IMAGE"`,
   `tripId`, 파일 정보를 전달한다.
2. 응답의 `uploadUrl`에 `requiredHeaders`를 사용해 파일을 PUT한다.
3. `POST /api/v1/media/complete`에 `purpose`, `tripId`,
   `storagePath`, `contentType`, `expectedCoverImageStoragePath`를 전달한다.
4. 완료 성공 후 여행 목록·상세를 다시 조회하면 `coverImageUrl`을 받을 수 있다.

커버이미지는 JPEG, PNG, WebP, HEIC, HEIF만 허용하며 최대 크기는 10 MB다.
업로드 signed PUT URL은 15분, 서버 업로드 세션은 1시간 동안 유효하다.

`expectedCoverImageStoragePath`는 업로드 발급 당시 서버가 기록한
커버 경로다. 최초 커버가 없으면 `null`이며, 완료 요청에서는 필드 자체를
반드시 포함해야 한다. 클라이언트는 발급 응답의 값을 그대로 전달한다.
서버는 저장된 세션 값과 요청값을 비교하고, 실제 CAS 조건에는 서버 값을 사용한다.

현재 커버 경로가 발급 당시 값과 달라졌으면
`TRIP_COVER_IMAGE_CONFLICT`(409)를 반환한다. 동일 경로의 완료 재시도는
멱등 처리한다. 세션이 만료되면 `MEDIA_UPLOAD_SESSION_EXPIRED`(410)를
반환하며 새 업로드 URL을 발급받아야 한다.

여행 문서에는 `coverImageStoragePath`를 저장하고, 목록·상세 응답에는
임시 signed GET URL인 `coverImageUrl`을 반환한다. 커버가 없는 기존 여행은
`coverImageUrl: null`이다. 이전 커버 blob은 교체 즉시 삭제하지 않으며,
별도의 참조 확인·정리 정책이 마련되기 전까지 Storage에 남을 수 있다.

### 직관 로그 수동 생성 및 동행 정보

직관 로그는 사용자가 `POST /api/v1/attendance-logs`를 호출해 직접 생성한다.
여행 종료 시 자동으로 생성하지 않는다.

생성은 `tripEndAt`을 한국시간(`Asia/Seoul`) 날짜로 변환했을 때
**여행 종료 다음 날 00:00 KST부터** 허용한다.
종료일 당일에는 실제 종료 시각이 지났더라도 생성할 수 없다.
조건을 충족하지 않으면 `ATTENDANCE_LOG_TRIP_NOT_COMPLETED`(409)를 반환한다.

기존 여행 소유권, 중복 로그, 활성 일정, 경기 존재 검사는 유지한다.
생성 시점의 확정 일정을 기반으로 DRAFT 로그와 Entry를 생성한다.

`mate`는 함께 직관한 사람을 기록하는 선택적 문자열이다.
`PATCH /api/v1/attendance-logs/{attendanceLogId}`에서 수정할 수 있으며
최대 100자다. 필드를 생략하면 기존 값을 유지하고, `null`이면 삭제한다.

직관 로그 목록·상세·아카이브 응답에 `mate`를 포함한다.
기존 문서에 필드가 없으면 `null`로 반환한다.

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
- `placeUrl`: 카카오 장소 고유 링크 또는 이름·좌표 기반 카카오맵 링크. 장소 목록·상세·찜·추천 후보·일정 Item에서 동일하게 제공합니다.
- `shortDescription`: 한 줄 표시용 장소 소개
- `overview`: 원본 장소 소개

`shortDescription`은 `overview`의 줄바꿈과 연속 공백을 한 줄로 정규화한 값이며,
원본 `overview`를 대체하지 않는다. 소개가 없으면 `null`일 수 있다.

## 여행 상태

`Trip.status`는 다음 상태만 사용한다. `ACTIVE`는 여행 상태가 아니며 더 이상
저장하지 않는다.

| 상태 | 의미 | 다음 정상 상태 |
| --- | --- | --- |
| `PLANNING` | 여행 생성 후 일정 입력·후보 선택 중 | `GENERATING` |
| `GENERATING` | 일정 생성 작업이 실행 중인 임시 상태 | `GENERATED` 또는 실패 전 상태 |
| `GENERATED` | 현재 일정 Plan이 생성된 상태 | 재생성 시 `GENERATING` |
| `COMPLETED` | 여행이 종료되어 확정된 상태 | 없음 |
| `CANCELLED` | 여행이 취소된 상태 | 없음 |

Cloud Run 강제 종료 등으로 `GENERATING`이 10분 이상 유지되면 다음 일정 생성
요청에서 오래된 작업으로 판단한다. `activePlanId`가 있으면 `GENERATED`, 없으면
`PLANNING`으로 원자적으로 복구한 뒤 새 생성을 시작한다.

`ItineraryPlan.status=ACTIVE`와 Trip의 `activePlanId`는 별도 개념이다. 전자는
여러 Plan 중 현재 사용 중인 Plan을 표시하고, 후자는 그 Plan ID를 가리킨다.

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
`playerPickId`, `stadiumId`, `playerName`, `playerPosition`, `place`, `recommendationNote`를
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

`homeSide`와 `result`는 직관 로그 생성 시점에 저장된 `supportTeamId`를 기준으로 계산한다.
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

기존 로그처럼 `supportTeamId` snapshot이 없는 경우에는 현재 사용자의 응원팀을 fallback으로 사용한다.

<!-- attendance-archive:end -->

<!-- attendance-stats:start -->

## 마이페이지 직관 통계 API

### GET `/api/v1/users/me/attendance-stats`

로그인한 사용자의 직관 로그와 실제 경기 결과를 기반으로 마이페이지용 직관 통계를 반환한다.

#### 집계 기준

- 직관 로그에 저장된 생성 시점 `supportTeamId` snapshot을 기준으로 집계한다.
- 기존 로그에 snapshot이 없으면 현재 사용자의 응원팀을 fallback으로 사용한다.
- 응원팀이 해당 경기에 참가하지 않은 `OTHER` 경기는 팀 승률 통계에서 제외한다.
- 점수가 없는 경기는 직관 횟수에는 포함하지만 승률 계산에서는 제외한다.
- 무승부는 승률 분모에 포함하며 승수에는 포함하지 않는다.
- 최근 10경기는 `gameStartAt` 기준 최신 순으로 최대 10건을 사용한다.
- 요일은 경기 시작 시각의 요일을 기준으로 집계한다.

#### 주요 응답 필드

| 필드 | 설명 |
| --- | --- |
| `awayTripCount` | 응원팀이 원정팀이었던 직관 횟수 |
| `awayWinCount` | 원정 직관 중 승리 횟수 |
| `homeAttendanceCount` | 응원팀이 홈팀이었던 직관 횟수 |
| `homeWinRate` | 홈 직관 승률. 집계 가능한 결과가 없으면 `null` |
| `awayWinRate` | 원정 직관 승률. 집계 가능한 결과가 없으면 `null` |
| `recent10AttendanceCount` | 최근 통계에 포함된 직관 수. 최대 10 |
| `recent10WinRate` | 최근 최대 10번 직관 승률 |
| `weekdayStats` | 월요일~일요일 요일별 직관 통계 |

#### `weekdayStats`

| 필드 | 설명 |
| --- | --- |
| `weekday` | `MONDAY` ~ `SUNDAY` |
| `attendanceCount` | 해당 요일 직관 횟수 |
| `winCount` | 승리 횟수 |
| `lossCount` | 패배 횟수 |
| `drawCount` | 무승부 횟수 |
| `winRate` | 해당 요일 승률. 집계 가능한 결과가 없으면 `null` |

승률 계산식:

`wins / (wins + losses + draws) * 100`

<!-- attendance-stats:end -->

### 기본 찜 컬렉션

모든 사용자는 시스템 기본 찜 컬렉션 `"저장됨"`을 가진다.

기본 컬렉션의 계약은 다음과 같다.

- 컬렉션 ID: `collection_saved`
- 이름: `저장됨`
- `isDefault`: `true`
- 이름 변경 불가
- 삭제 불가

일반 사용자가 `"저장됨"`이라는 이름으로 별도의 컬렉션을 생성할 수는 있으며,
이 컬렉션은 `isDefault=false`이므로 시스템 기본 컬렉션과 구분된다.

신규 사용자 프로필 생성 시 기본 컬렉션 생성을 시도한다.
기본 컬렉션 생성 중 일시적인 Firestore 오류가 발생하더라도 사용자 프로필
생성 자체는 성공 상태를 유지한다.

`GET /api/v1/users/me/favorite-collections`를 호출하면 기본 컬렉션 존재를
다시 보장하므로, 기존 사용자나 이전 생성 실패 사용자도 별도 마이그레이션 없이
기본 `"저장됨"` 컬렉션이 생성된다.

기본 컬렉션 생성은 고정 ID와 Firestore `create`를 사용하여 멱등하게 처리하며,
반복 호출해도 중복 기본 컬렉션을 생성하지 않는다.

`FavoriteCollectionResponse`에는 다음 필드가 추가된다.

- `isDefault`: 시스템 기본 찜 컬렉션 여부

기본 컬렉션에 대해 이름 변경 또는 삭제를 시도하면
`409 DEFAULT_FAVORITE_COLLECTION_IMMUTABLE`을 반환한다.

기존 Firestore 컬렉션 문서에 `isDefault` 필드가 없는 경우에는
`false`로 취급한다.

### 경기 목록 기간 조회

`GET /api/v1/games`는 기존 단일 날짜 조회와 함께 기간 조회를 지원합니다.

- `date=2026-08-15`: 한국시간 기준 해당 날짜의 경기 조회
- `from=2026-08-01&to=2026-08-31`: 시작일과 종료일을 모두 포함한 기간 조회
- `from`과 `to`는 함께 입력해야 합니다.
- `date`와 `from/to`는 동시에 사용할 수 없습니다.
- 시작일이 종료일보다 늦으면 `422 INVALID_GAME_DATE_RANGE`를 반환합니다.
- 기존 `teamId`, `stadiumId`, `status` 필터와 함께 사용할 수 있습니다.
- 날짜 조건이 없으면 기존 전체 조회 동작을 유지합니다.
- 날짜 조건이 있으면 한국시간 날짜 범위를 UTC로 변환하여 Firestore `gameStartAt` 범위 쿼리로 조회합니다.
- 응답은 기존 `ListSuccessResponse[GameResponse]` 형식을 유지합니다.

### 공지사항 조회

#### GET /api/v1/notices

공개된 공지사항 목록을 최신 게시일순으로 조회합니다.

- 인증 없이 조회할 수 있습니다.
- Firestore `notices` 컬렉션에서 `isPublished=true`인 문서만 반환합니다.
- 목록에는 `noticeId`, `title`, `publishedAt`을 반환하며 본문은 포함하지 않습니다.
- `publishedAt` 내림차순으로 정렬하고, 같은 게시일이면 `noticeId` 내림차순으로 정렬합니다.
- 응답은 `ListSuccessResponse[NoticeSummaryResponse]` 형식입니다.
- 현재 페이지네이션은 지원하지 않으며 `nextPageToken`은 `null`입니다.

#### GET /api/v1/notices/{noticeId}

공지사항 ID로 공개된 공지사항의 상세정보를 조회합니다.

- 응답에는 `noticeId`, `title`, `publishedAt`, `content`를 반환합니다.
- 존재하지 않거나 비공개인 공지는 `404 NOTICE_NOT_FOUND`를 반환합니다.
- 응답은 `SuccessResponse[NoticeDetailResponse]` 형식입니다.

#### Firestore notices 문서

| 필드 | 타입 | 설명 |
|---|---|---|
| title | string | 공지 제목 |
| content | string | 공지 본문 |
| isPublished | boolean | 공개 여부 |
| publishedAt | timestamp \| null | 게시일 |
| createdAt | timestamp | 생성일 |
| updatedAt | timestamp | 수정일 |

공개된 문서는 `publishedAt`이 반드시 있어야 합니다. 이번 구현은 조회 전용이며 관리자 작성·수정·삭제 API는 포함하지 않습니다.

### 알림 설정 및 동의 변경 이력

이번 구현은 알림 수신 설정과 변경 이력 관리만 지원합니다. 실제 푸시 알림 발송은 포함하지 않습니다.

#### GET /api/v1/users/me/notification-settings

인증된 사용자의 현재 알림 설정을 조회합니다. 설정 문서가 없으면 기본값을 생성합니다.

| 필드 | 기본값 | 설명 |
|---|---|---|
| gameReminderEnabled | true | 경기 알림 |
| tripReminderEnabled | true | 여행 일정 알림 |
| marketingEnabled | false | 마케팅 알림 |
| updatedAt | 현재 시각 | 설정 수정 시각 |

응답은 `SuccessResponse[NotificationSettingsResponse]` 형식입니다.

#### PATCH /api/v1/users/me/notification-settings

알림 설정을 부분 수정합니다.

요청 예시: `{"marketingEnabled": true}`

- 하나 이상의 설정을 입력해야 합니다.
- 입력하지 않은 설정은 기존 값을 유지합니다.
- 설정 값에 `null`을 사용할 수 없습니다.
- 실제 값이 변경된 항목만 변경 이력을 생성합니다.
- 설정과 변경 이력은 Firestore batch로 함께 저장합니다.
- 응답은 `SuccessResponse[NotificationSettingsResponse]` 형식입니다.

#### GET /api/v1/users/me/notification-consent-history

인증된 사용자의 알림 설정 변경 이력을 최신순으로 조회합니다.

이력에는 `historyId`, `consentType`, `previousEnabled`, `enabled`, `changedAt`을 반환합니다. `consentType`은 `GAME_REMINDER`, `TRIP_REMINDER`, `MARKETING` 중 하나입니다.

응답은 `ListSuccessResponse[NotificationConsentHistoryResponse]` 형식이며, 현재 페이지네이션은 지원하지 않습니다.

#### Firestore 저장 구조

- `users/{userId}/settings/notifications`: 현재 알림 설정
- `users/{userId}/notificationConsentHistory/{historyId}`: 설정 변경 이력

기본 설정은 경기·여행 알림을 켜고 마케팅 알림을 끈 상태로 생성합니다.

### 찜 컬렉션 요약 및 장소별 역조회

기존 개인 찜 컬렉션 API를 유지하면서 목록 및 이름 변경 응답에 요약 정보를 추가합니다.

#### 컬렉션 요약 필드

`FavoriteCollectionResponse`에 다음 필드가 추가됩니다.

| 필드 | 타입 | 설명 |
|---|---|---|
| placeCount | integer | 컬렉션에 저장된 실제 장소 개수 |
| representativePlaceName | string | null | 첫 번째 저장 장소의 이름 |
| thumbnailUrl | string | null | 첫 번째 저장 장소의 대표 이미지 |

- 빈 컬렉션은 `placeCount=0`, `representativePlaceName=null`, `thumbnailUrl=null`입니다.
- 기존 `items` 문서를 조회하여 개수를 계산하므로 별도 카운터나 데이터 마이그레이션은 필요하지 않습니다.
- 대표 장소는 기존 저장 시각 오름차순의 첫 번째 장소입니다.
- 장소 스냅샷이 있으면 외부 API를 호출하지 않습니다.
- 기존 ID 전용 찜 문서는 TourAPI 상세조회로 스냅샷을 보충합니다.
- 대표 장소 조회가 실패해도 컬렉션 목록 전체를 실패시키지 않고 대표 정보를 null로 반환합니다.

#### GET /api/v1/users/me/favorite-collections/by-place/{placeId}

특정 TourAPI 장소가 현재 인증된 사용자의 어떤 찜 컬렉션에 저장되어 있는지 조회합니다.

**Path parameter**

- `placeId`: TourAPI 장소 ID. 예: `tour_1603175`

**성공 응답 예시**

    {
      "success": true,
      "data": {
        "placeId": "tour_1603175",
        "collectionIds": ["collection_saved", "collection_001"],
        "count": 2
      }
    }

- 같은 장소가 여러 컬렉션에 저장되어 있으면 모든 컬렉션 ID를 반환합니다.
- 저장된 컬렉션이 없으면 `collectionIds=[]`, `count=0`입니다.
- 조회 대상은 현재 인증된 사용자의 컬렉션으로 제한됩니다.
- TourAPI 장소 ID가 아니면 422 `INVALID_FAVORITE_PLACE`를 반환합니다.
- 별도 역조회 인덱스는 저장하지 않고 현재 컬렉션의 Item 존재 여부를 조회합니다.
- 실제 TourAPI 호출이나 Firestore E2E는 이번 단위 테스트에서 검증하지 않았습니다.

### 여행 일정 장소의 날짜 이동

`PATCH /api/v1/trips/{tripId}/plan/items/{itemId}/time`은 PLACE 항목의
시작시간 변경뿐 아니라 다른 날짜로의 이동에도 사용한다.

요청 예시:

    {
      "scheduledStartAt": "2026-08-16T14:00:00+09:00"
    }

- `scheduledStartAt`의 날짜가 기존 날짜와 같으면 해당 PLACE의 시작시간을 변경한다.
- 날짜가 다르면 해당 PLACE를 대상 날짜의 일정으로 이동한다.
- 이동한 PLACE의 기존 방문시간 길이는 유지한다.
- 이동 후 출발 날짜와 대상 날짜의 이동정보 및 sequence를 다시 계산한다.
- 변경된 PLACE는 `isFixed=true`가 된다.
- 대상 날짜가 현재 Plan에 없으면 `404 ITINERARY_DAY_NOT_FOUND`를 반환한다.
- 대상 날짜에 동일한 장소가 이미 있으면 `400 ITINERARY_EDIT_INVALID`를 반환한다.
- ARRIVAL_POINT, DEPARTURE_POINT, STADIUM, ACCOMMODATION Anchor는 이동할 수 없다.

### 직관 로그 미작성 여행 조회

홈 화면에서 직관 로그 생성 안내 여부를 판단하기 위한 API입니다.

**GET /api/v1/attendance-logs/pending-trips**

- 인증: Firebase ID Token 필요
- 응답: `SuccessResponse[AttendanceLogRequiredResponse]`
- `attendanceLogRequired`: 생성 가능한 미작성 여행이 하나 이상이면 `true`
- `trips`: 최근 종료된 여행부터 반환

응답 예시:

    {
      "success": true,
      "data": {
        "attendanceLogRequired": true,
        "trips": [
          {
            "tripId": "trip_001",
            "title": "부산 원정 여행",
            "tripEndAt": "2026-08-15T23:00:00+09:00"
          }
        ]
      }
    }

대상 조건:

- 현재 로그인 사용자의 여행
- 취소되지 않은 여행
- 한국시간 기준 여행 종료 다음 날 00:00 이후
- `activePlanId`가 존재하고 해당 Plan이 `ACTIVE` 상태
- 삭제되지 않은 직관 로그가 없는 여행

삭제된 직관 로그는 존재하지 않는 것으로 취급합니다.
취소 경기의 빈 티켓 생성 정책은 별도 요구사항으로 처리합니다.


### Firebase 이름 저장

최초 사용자 프로필 생성 시 이름은 다음 우선순위로 저장합니다.

1. 요청 본문의 `name`
2. Firebase ID Token의 `name` 클레임
3. 이름이 없으면 `null`

Firebase `displayName`은 ID Token에서 일반적으로 `name` 클레임으로 전달됩니다.
호환성을 위해 `displayName` 클레임도 fallback으로 확인합니다.

이름은 앞뒤 공백을 제거하며, 유효한 Firebase 이름이 없으면 `null`을 저장합니다.
기존 `POST /api/v1/users/me/bootstrap` 요청 계약은 유지됩니다.
이후 `PATCH /api/v1/users/me`로 이름을 수정하거나 삭제할 수 있습니다.

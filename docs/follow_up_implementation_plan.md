# 후속 구현 계획

## 1. 선수 추천 장소 통합

- `player_pick_` ID를 찜, 찜 조회, 여행 후보 Import, 일정 생성에서 지원한다.
- `recommendation-candidates`에 해당 경기장 선수 추천 장소를 함께 반환한다.
- 선수 추천 장소임을 응답에서 식별할 수 있는 태그와 선수 정보를 제공한다.
- 거리와 영업시간 조건이 비슷하면 일반 TourAPI 후보보다 선수 추천을 우선한다.
- 운영 조회에서는 TourAPI를 호출하지 않고 Firestore `placeSnapshot`만 사용한다.
- 배포 전 검사에서 snapshot이 하나라도 빠지면 실패로 처리한다.

## 2. 선수 추천 장소 사전 보강과 외부 링크

- 사용자 요청 시점이 아니라 사전 작업으로 Firestore `placeSnapshot`을 완성한다.
- 이름, 주소, 좌표가 충분히 일치하는 TourAPI 장소가 있으면 상세·이미지·영업시간을 결합한다.
- TourAPI에 없는 장소는 확인 가능한 정보를 관리자 입력으로 보완하고 출처와 확인 시각을 기록한다.
- 카카오 Local API가 제공한 장소 URL을 카카오맵 확인 링크로 저장한다.
- 확인할 수 없는 정보는 추측하지 않고 `MISSING` 상태를 유지한다.

## 3. 추천 후보 조회 계약

- 검색과 필터는 `/trips/{tripId}/recommendation-candidates`가 만든 추천 후보 안에서 적용한다.
- `pageSize`, `pageToken`, `filterId`, `keyword`를 지원한다.
- 내부 `category` 필터는 외부 장소 조회 API에서 제거했다.
- 중복 기능인 TourAPI `classifications` 공개 엔드포인트를 제거했다.
- 선수 추천은 통합 필터의 `PLAYER_PICK`으로 조회할 수 있다.

## 4. 경기 월별 조회

- `GET /api/v1/games?year=YYYY&month=M` 형식을 지원한다.
- 한국시간 월 시작 이상, 다음 달 시작 미만으로 Firestore에서 범위 조회한다.
- 기존 구단, 구장, 상태 필터와 함께 사용할 수 있게 한다.

## 5. 하루 일정 재생성

- `POST /api/v1/trips/{tripId}/plan/days/{date}/regenerate`를 추가한다.
- 같은 Plan에서 대상 날짜만 교체하고 `updatedAt`을 갱신한다.
- 다른 날짜, Anchor, `isFixed=true` Item은 보존한다.
- 대상 날짜의 이동시간과 순서를 다시 계산한다.

## 재생성 시 선택 장소 정책

- Anchor와 `isFixed=true` Item만 보존한다.
- 재생성 대상의 고정되지 않은 사용자 선택·자동 추천 장소는 이번 후보에서 제외한다.
- 사용자 선택 장소는 영구 거절 목록에 넣지 않는다.
- 고정되지 않은 자동 추천 장소만 재추천 제외 이력에 기록한다.
- 하루 재생성은 다른 날짜와 그 Item ID를 변경하지 않는다.

## 여행 선호 설문 계약

- `preferredCategories`: `FOOD`, `ACTIVITY`, `SHOPPING`, `EXPERIENCE`,
  `RELAXATION`, `HISTORY`, `NATURE`, `CULTURE` 중 복수 선택
- `scheduleDensity`: 널널한 일정은 `LIGHT`, 촘촘한 일정은 `DENSE`
- `MODERATE`는 기본값과 기존 문서 호환을 위해 유지한다.
- 역할이 겹치던 기존 여행 스타일 필드는 API, 내부 모델, Firestore 신규 문서에서 제거한다.
- 기존 테스트 여행은 호환 대상으로 유지하지 않고 새 여행을 생성해 검증한다.

선호 카테고리는 실행 가능한 후보 중 우선순위에 반영한다. 식사 시간, 영업시간,
Anchor 도착 조건과 이동 가능성은 선호보다 우선한다. 카테고리 범위는 다음과 같다.

- `FOOD`: 음식점·카페 전체(`FD`)
- `ACTIVITY`: 레포츠 및 활동 시설(`LS`, 관련 `VE02/VE04/VE10`)
- `SHOPPING`: 쇼핑(`SH`)
- `EXPERIENCE`: 체험관광(`EX`, 웰니스 `EX05` 제외)
- `RELAXATION`: 웰니스 관광(`EX05`)
- `HISTORY`: 역사 관광(`HS`)
- `NATURE`: 자연 관광(`NA`)
- `CULTURE`: 문화시설 및 축제·공연·행사(`VE07`, `EV`)

일정 밀도는 이동시간 비율과 Anchor 앞에 남겨둘 최소 시간에만 반영하고 자동 추천
개수 상한으로 사용하지 않는다.

## 배포 버전 확인

`GET /api/v1/health`는 `version`, `commitSha`, `deployedAt`을 반환한다.
Cloud Run 배포 시 `APP_COMMIT_SHA`, `APP_DEPLOYED_AT`을 주입하며 로컬에서
설정하지 않으면 두 값은 `null`이다.

# 3주차 합의 반영 및 다음 작업 계획

## 기준 상태

- 기준 브랜치: `main`
- 확인 커밋: `80458ec` (`Merge pull request #20`)
- 3주차 경로 최적화, 자동 추천 삽입, 회의 시연 자료와 확정 정책 문서는
  `main`에 병합되어 있다.

## 3주차 회의 확정 정책

### 개인 찜 컬렉션

- 구단별 컬렉션은 사용하지 않고 사용자 개인 컬렉션만 제공한다.
- 찜 컬렉션에는 TourAPI 기반 장소만 저장한다.
- 일정에 컬렉션을 불러올 때 선택한 경기·경기장의 지역과 일치하는 장소만
  자동으로 여행 후보에 포함한다.
- 지역 필터링은 컬렉션 자체에 구단·구장 메타데이터를 저장하는 방식이 아니라,
  Game과 Stadium의 지역 및 각 Place의 주소·좌표를 조회해 수행한다.
- 자동으로 불러온 장소는 일반 여행 후보이며 사용자가 제외하거나
  `isRequired=true`로 변경할 수 있다.

### TourAPI와 Kakao 역할

- 찜, 여행 후보, 코스 및 자동 추천은 TourAPI 장소로만 구성한다.
- Kakao 검색 결과를 독립 장소로 생성하거나 찜·일정 후보로 제공하지 않는다.
- Kakao Local API는 TourAPI 상세 장소의 빈 주소·전화번호 또는 `OTHER`
  카테고리를 안전하게 보충하는 데만 사용한다.
- 보충 후에도 TourAPI의 `placeId`, `source`, `sourceContentId`를 유지한다.
- Kakao Local이 보장하지 않는 이미지·소개·영업시간·휴무일은 보충하지 않는다.

## 현재 구현 상태

### 완료

- TourAPI 주변·상세·소개·이미지 조회와 내부 `Place` 변환
- TourAPI 신분류 코드 `lclsSystem1/2/3` 적용
- TourAPI 상세정보에 대한 Kakao 보충
- 요일별 영업시간·휴무일과 입장 마감 제약
- ODsay 대중교통 및 도보 추정시간 비교, 실패 시 거리 기반 fallback
- 다일정 후보 배정, Greedy Insertion, 2-opt
- 필수·일반 후보 우선 배정 및 전달받은 추천 후보의 빈 시간 자동 삽입
- `ItineraryPlan` 저장 스키마의 `itemId`, `isFixed`, ACTIVE/ARCHIVED 계약
- 여행 기본정보 CRUD

### 부분 완료

- 장소 추천: 추천 후보를 일정에 삽입하는 알고리즘은 완료했지만 실제
  TourAPI·저장 Place에서 후보를 선별하는 서비스는 연결되지 않았다.
- 개인 찜 컬렉션: 스키마와 정책만 존재하며 Repository·Service·API는 없다.
- 일정 계획: 저장 모델은 있으나 생성 API, Repository 및 Firestore 저장은 없다.
- 일정 수정·재생성: 정책과 필드는 확정됐지만 실제 수정 API와 고정 기반
  재최적화는 없다.

## 지난주에서 이관된 작업

### 우선순위 1 — 실제 일정 생성 세로 연결

1. `POST /trips/{tripId}/itineraries` 구현
2. Trip, Game, Stadium, 선택 후보를 조회해 내부 `TripInput` 구성
3. 실제 이동시간 Matrix 생성
4. 추천 후보 서비스 호출 후 `generate_itinerary()` 실행
5. 결과에 `itemId`를 생성해 `itineraryPlans`에 저장
6. 기존 ACTIVE Plan을 ARCHIVED로 바꾸고 Trip의 `activePlanId`와 상태 갱신

담당자 A의 Repository·Firestore transaction 작업과 담당자 B의 추천 후보·알고리즘
연결이 모두 필요하다.

### 우선순위 2 — 개인 컬렉션과 여행 후보

1. 개인 찜 컬렉션 Repository·Service·API 구현
2. 찜 Item에는 TourAPI `placeId`만 허용
3. `trips/{tripId}/placeCandidates` CRUD 구현
4. Game·Stadium 지역과 Place 주소·좌표를 이용한 컬렉션 불러오기 필터 구현
5. 불러온 후보의 제외 및 `isRequired` 변경 API 구현

### 우선순위 3 — 실제 추천 후보 선별

1. 경기장·도착지 주변 TourAPI 장소 조회
2. 개인 컬렉션과 이미 선택된 장소, 중복 장소 제외
3. 잘못된 좌표, 휴무일, 해석 가능한 영업시간과 입장 마감 사전 필터
4. 필수·일반 사용자 후보에 높은 우선순위를 유지
5. 남는 시간의 위치·카테고리·추가 이동시간을 기준으로 추천 후보 정렬
6. 정렬된 후보를 현재 자동 삽입 알고리즘에 전달

추천 후보를 일정에 넣는 로직은 이미 있으므로, 이 단계에서는 알고리즘을 다시
작성하지 않고 실제 후보 공급 계층을 구현한다.

### 우선순위 4 — 일정 편집과 재생성

1. Item 시간 수정, 삭제·교체, 순서 변경
2. 수동 장소 추가 시 전체 최적화 없이 앞뒤 이동시간·시간표만 재계산
3. 숙소 Item 이동 시 30분 체류와 앞뒤 이동시간 적용
4. `isFixed=true` Item의 날짜·순서를 유지하는 부분 재최적화
5. 고정되지 않은 자동 추천만 제거하고 다시 채우는 재생성
6. Anchor 삭제·이동 제한과 시간 충돌 경고

### 우선순위 5 — 검증과 성능

- 당일치기, 1박 2일, 2박 3일 및 날짜 경계 테스트
- 실제 Game·Stadium·TourAPI·ODsay·Firestore 통합 테스트
- 후보 10·20·30개 실행시간 측정과 제한값 결정
- 외부 API 실패, 빈 추천 결과, 필수 장소 충돌 시나리오 테스트
- Firebase 인증 없이 실행되는 단위/API 테스트와 실제 Firebase 통합 테스트 분리

## 바로 진행할 순서

1. 담당자 A와 일정 생성 API 및 Firestore 저장 transaction 경계를 확정한다.
2. 담당자 B는 실제 추천 후보를 만드는 `RecommendationService`를 구현한다.
3. 개인 컬렉션과 여행 후보 API가 준비되면 지역 필터를 연결한다.
4. 위 입력들을 일정 생성 Application Service에서 조합한다.
5. 실제 생성·저장 흐름이 안정화된 뒤 편집과 고정 기반 재생성을 구현한다.

현재 가장 먼저 단독으로 진행할 수 있는 담당자 B 작업은 TourAPI 장소만을 대상으로
하는 실제 추천 후보 선별 서비스와 그 단위 테스트다.

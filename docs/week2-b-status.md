# Week 2 담당자 B 진행 현황 및 회의 시연안

## 1. 구현 완료 내용

### TourAPI Adapter

- 위치·반경 기반 주변 장소 조회
- 공통정보·소개정보·이미지정보를 결합한 장소 상세 조회
- TourAPI 응답을 내부 `Place` 모델로 변환
- 음식점·관광지·숙박·문화시설·쇼핑·축제·레포츠 카테고리 매핑
- 중복 장소와 잘못된 좌표 항목 제거
- 이미지·영업시간이 없을 때 `null` fallback
- timeout, 빈 응답, 호출 제한, 업무 오류 처리
- 프로세스 메모리 TTL 캐시(기본 5분)

상세 조회는 프론트가 `nearby` 응답의 내부 `placeId`를 그대로 전달한다.

```http
GET /api/v1/tour/places/tour_1603175
```

백엔드는 `tour_1603175`에서 TourAPI 원본 ID `1603175`를 추출하고, 공통정보 응답에서 `contentTypeId`를 확인한 뒤 소개정보와 이미지정보를 조회한다. `KorService2`에서 허용하지 않는 구버전 `defaultYN`, `subImageYN` 파라미터는 제거했다. 아시아공원(`tour_1603175`)으로 공통·소개·이미지 API의 `0000 OK`를 확인했다.

### 지도·이동시간

- ODsay 대중교통 이동시간 조회 Client
- 출발지·도착지 좌표 요청과 응답 시간 파싱
- 좌표 쌍 기준 5분 캐시로 동일 경로 중복 호출 방지
- ODsay 실패 시 Haversine 직선거리 기반 예상시간 fallback
- 장소 간 이동시간 Matrix 생성
- 실제 ODsay Server Key로 잠실→고척 및 부산 일정 경로 검증

### 일정 생성 알고리즘 v0.1

- 도착지·출발지·숙소·경기장 Anchor 생성
- 장소별 기본 체류시간과 영업시간 적용
- 경기 시작 40분 전 도착 조건
- 출발 교통편 1시간 전 도착 조건
- 필수 장소 우선, 이후 가까운 장소 우선 배정
- 방문 불가능 장소 제외와 기본 제외 사유 반환
- 가짜 Matrix 및 실제 ODsay Matrix 일정 생성 검증

### 개발 데이터와 계약

- 구장 9개와 개발용 경기 5개 Firestore 샘플 JSON
- `TripInput`, `ItineraryResult`, 날짜별 일정과 Item 구조
- `selectedPlaces[{placeId, isRequired}]` 구조
- `ARRIVAL_POINT`, `PLACE`, `ACCOMMODATION`, `STADIUM`, `DEPARTURE_POINT` Item type
- Mock 입력·출력 및 Week 2 생성 결과 JSON

## 2. 부분 완료 또는 후속 작업

- KBO 경기 데이터: 개발 Seed만 완료했으며 실제 확정 일정 수집원과 갱신 주기는 미정
- TourAPI 상세정보: 아시아공원은 검증했으며 음식점·숙박 등 다양한 유형의 추가 확인 필요
- 캐시: 현재 단일 서버 메모리 방식이며 다중 인스턴스 배포 시 Redis 등 검토
- 알고리즘: 규칙 기반 v0.1이며 다양한 여행 조건과 실제 교통시간 검증 필요
- 여행 생성 API와 Firestore 저장 연결은 담당자 A의 Application Service·Repository 연결 필요

## 3. 회의 설명 순서

1. TourAPI 원본을 내부 `Place`로 변환하는 이유와 필드 매핑 설명
2. 주변 장소 조회 결과의 `placeId`를 상세 조회에 그대로 사용하는 흐름 설명
3. TourAPI 공통·소개·이미지 응답의 결합과 fallback 설명
4. ODsay 이동시간과 API 실패 시 직선거리 fallback 설명
5. Anchor와 시간 제약을 이용한 일정 생성 v0.1 설명
6. 아직 연결되지 않은 여행 생성 API·Firestore 저장 영역을 담당자 A 작업으로 구분

## 4. 회의 시연 순서

### A. 지금 바로 가능한 시연 — Firebase 서비스 계정 불필요

#### TourAPI 주변 장소와 상세 조회

```http
GET /api/v1/tour/nearby?longitude=127.0719&latitude=37.5122&radius=2000
GET /api/v1/tour/places/tour_1603175
```

확인할 내용:

- `placeId`, 이름, 내부 카테고리, 좌표, 주소
- `sourceContentId`, `contentTypeId`
- 상세 조회의 `overview`, 이미지, 운영정보
- 이미지·영업시간이 없을 때 `null` 반환
- 상세 조회에는 별도 `contentTypeId` 입력이 필요하지 않음

#### ODsay 단일 경로 확인

```powershell
uv run python -m scripts.check_odsay
```

#### 가짜 이동시간 Matrix 일정 생성

```powershell
uv run python -m scripts.demo_itinerary
```

#### 실제 ODsay 이동시간 일정 생성

```powershell
uv run python -m scripts.demo_itinerary --live
```

`TOUR_API_KEY`와 `ODSAY_API_KEY`는 로컬 `.env`에 있어야 하며 실제 값을 화면에 노출하지 않는다.

### B. 조건부 시연 — Firebase 서비스 계정 필요

> **회의 시점에는 서비스 계정 키가 없어 실행 보류. 팀원에게 회의 후 전달받아 검증한다.**

다음 항목은 `secrets/firebase-service-account.json`이 있어야 실제 Firestore와 연결된다.

- 경기·구장·구단 Seed 저장
- `GET /api/v1/games`
- 날짜·구단·구장·경기 상태 필터 조회
- `GET /api/v1/games/{gameId}` 상세 조회
- 실제 Firestore 기반 Trip API

키를 받은 후 실행 순서:

```powershell
uv run python -m scripts.seed_teams
uv run python -m scripts.seed_stadiums
uv run python -m scripts.seed_games
uv run uvicorn app.main:app --reload
```

Firebase 연결 시연을 하지 못할 경우 `samples/firestore/games.json`, `samples/firestore/stadiums.json`과 mock 기반 테스트 결과로 데이터 구조만 설명한다. Firebase 웹용 `firebaseConfig`는 FastAPI의 Admin SDK 인증을 대신할 수 없다.

## 5. 담당자 A 선행 또는 연결 작업

- Trip·Game·Stadium·선택 Place를 `TripInput`으로 조합하는 Application Service
- `POST /api/v1/trips/{tripId}/itineraries` 연결
- Trip 상태 `PLANNING → GENERATING → GENERATED` 전환과 실패 복구
- UID 소유권 검증
- `ItineraryPlanRepository`와 Firestore transaction/batch 저장
- 새 Plan을 `ACTIVE`, 이전 Plan을 `ARCHIVED`로 처리
- 저장 단계에서 일정 Item의 `itemId` 생성
- Swagger 최종 요청·응답 예시 작성

## 6. 프론트엔드와 합의·검토할 내용

### 장소 API

- 주변 조회는 좌표와 반경을 받고 첫 20개를 반환하는 현재 범위 유지 여부
- 잠실 좌표 기본값을 시연 이후에도 유지할지, 실제 앱에서는 필수 좌표로 바꿀지
- 상세 조회는 `nearby`의 `placeId`를 그대로 전달
- `thumbnailUrl`, `openTime`, `closeTime`, `closedDaysText`의 `null` UI 처리
- `distanceMeters`는 검색 기준점에 따라 달라지므로 장소 영구 저장 필드로 사용하지 않음
- 이름 검색이 필요하면 `/tour/places/{placeId}`가 아닌 별도 검색 API 설계

### 여행 생성 요청

- `selectedPlaces`의 `{placeId, isRequired}` 확정
- 도착지·출발지·숙소를 좌표와 주소로 전달하는 방식
- 경기 선택 시 `gameId`와 `stadiumId`를 프론트가 어느 단계에서 전달할지
- 필수 장소가 방문 불가능할 때 전체 실패 또는 제외 결과 반환 중 어떤 UX를 사용할지

### 일정 생성 응답

- 날짜별 Item type에 따른 화면 표현과 아이콘
- `excludedPlaces`와 제외 사유의 사용자 표시 방식
- 예상 이동시간과 ODsay 이동시간을 구분할 `travelTimeSource` 필드 추가 여부
- 일정 수정 기능을 위해 저장 후 생성되는 `itemId` 사용 방식
- 이미지·운영시간이 없는 장소의 fallback UI

## 7. 회의 완료 후 확인

- Firebase 서비스 계정 키를 안전한 경로로 전달받기
- 로컬 `secrets/firebase-service-account.json`에 저장하고 Git 제외 여부 확인
- Seed와 경기 API 실호출
- 전체 테스트 재실행
- 프론트 협의 결과를 API 명세서 v1.0에 반영하고 필드명 동결

## 8. 회의 설명 대본

### 1) TourAPI 원본을 내부 Place로 변환하는 이유

> TourAPI가 내려주는 필드명과 카테고리는 우리 앱에서 그대로 사용하기 어렵기 때문에 Adapter 계층에서 내부 `Place` 모델로 변환했습니다. 예를 들어 TourAPI의 `contentid`는 내부 `placeId`와 `sourceContentId`로, `mapy`와 `mapx`는 `latitude`와 `longitude`로 변환합니다. `contenttypeid`도 그대로 프론트에 판단을 맡기지 않고 `TOURIST_SPOT`, `RESTAURANT`, `ACCOMMODATION` 같은 내부 카테고리로 바꿉니다. 이렇게 하면 향후 Kakao나 로컬 데이터가 추가돼도 프론트와 알고리즘은 동일한 `Place` 형식만 사용하면 됩니다.

설명할 대표 매핑:

| TourAPI 원본 | 내부 Place | 설명 |
| --- | --- | --- |
| `contentid` | `placeId`, `sourceContentId` | 내부 ID는 `tour_{contentid}` 형식 |
| `title` | `name` | 장소명 |
| `mapy` | `latitude` | 위도 |
| `mapx` | `longitude` | 경도 |
| `addr1` + `addr2` | `address` | 전체 주소 |
| `zipcode` | `postalCode` | 우편번호 |
| `tel` | `telephone` | 전화번호 |
| `firstimage` | `thumbnailUrl` | 대표 이미지 |
| `dist` | `distanceMeters` | 검색 기준점으로부터의 거리 |
| `contenttypeid` | `category`, `contentTypeId` | 내부 카테고리와 원본 유형 |

### 2) nearby 결과에서 상세 조회로 이어지는 흐름

> 프론트가 좌표와 반경으로 `nearby`를 호출하면 내부 `Place` 목록이 반환됩니다. 사용자가 목록에서 장소를 선택하면 프론트는 응답에 있던 `placeId`, 예를 들어 `tour_1603175`를 상세 API에 그대로 전달합니다. 프론트가 TourAPI의 원본 `contentId`나 `contentTypeId`를 별도로 조합할 필요는 없습니다. 백엔드가 `tour_` 접두사를 통해 데이터 출처를 확인하고 원본 ID를 추출합니다.

```text
GET /tour/nearby
→ placeId: tour_1603175
→ GET /tour/places/tour_1603175
→ 백엔드가 contentId 1603175 추출
→ 내부 Place 상세 반환
```

### 3) 공통·소개·이미지 응답 결합과 fallback

> TourAPI의 장소 상세정보는 한 번의 호출로 모두 내려오지 않습니다. 공통정보에서는 이름·주소·좌표·소개를 받고, 콘텐츠 유형별 소개정보에서는 운영시간과 휴무일을 받고, 이미지 API에서는 추가 이미지를 받습니다. Adapter가 이 세 응답을 병렬 또는 순차적으로 조합해 하나의 `Place`로 반환합니다. 이미지가 없으면 `thumbnailUrl=null`, 운영시간을 확인할 수 없으면 `openTime`과 `closeTime`을 `null`로 반환합니다. 운영시간이 없다고 24시간 영업으로 추정하지 않습니다.

> 아시아공원 `tour_1603175`로 공통·소개·이미지 응답이 모두 `0000 OK`인 것을 확인했습니다. 또한 `KorService2`에서 허용하지 않는 구버전 파라미터 때문에 발생하던 502 오류를 수정했고, 향후 TourAPI 업무 오류가 발생하면 실제 `resultCode`와 `resultMessage`를 확인할 수 있게 보완했습니다.

### 4) ODsay 이동시간과 직선거리 fallback

> 일정의 장소 간 이동시간은 우선 ODsay 대중교통 API로 조회합니다. 동일한 좌표 쌍은 5분 동안 캐시해 중복 호출을 줄입니다. ODsay가 timeout이나 외부 오류로 실패해도 일정 전체를 바로 실패시키지 않고, 두 좌표의 직선거리를 계산한 뒤 예상 이동시간으로 대체합니다. 실제 ODsay 시간과 추정시간을 프론트에서 구분해 보여줄지는 `travelTimeSource` 필드를 추가할지와 함께 합의가 필요합니다.

### 5) Anchor와 시간 제약 기반 일정 생성 v0.1

> 1차 알고리즘은 반드시 지켜야 하는 지점을 Anchor로 먼저 배치합니다. 여행 도착지, 출발지, 숙소와 경기장이 Anchor입니다. 경기장은 경기 시작 40분 전까지 도착하도록 하고, 마지막 출발지는 교통편 출발 1시간 전까지 도착하도록 제한합니다. 그 사이에 사용자가 선택한 장소를 배치하며, 필수 장소를 먼저 고려한 뒤 이동거리가 가까운 장소를 우선합니다. 장소의 체류시간과 영업시간도 확인하고, 배치할 수 없는 장소는 삭제하지 않고 제외 사유와 함께 결과에 반환합니다.

> 현재 버전은 최적해를 보장하는 완성형 추천 알고리즘이 아니라, 정해진 규칙이 실제 입력과 가짜 또는 실제 이동시간 Matrix에서 동작하는지 검증하는 `greedy-anchor-v0.1`입니다.

### 6) 담당자 A 연결 영역 구분

> 제가 구현한 범위는 외부 장소 데이터, 이동시간 Matrix와 순수 일정 생성 함수까지입니다. 알고리즘은 Firestore나 TourAPI를 직접 호출하지 않고 준비된 입력만 받아 결과를 반환합니다. 실제 서비스에서는 담당자 A의 Application Service가 Trip·Game·Stadium과 선택 장소를 조회해 `TripInput`을 만들고 알고리즘을 호출해야 합니다. 이후 결과를 `itineraryPlans`에 저장하고 Trip 상태와 활성 Plan을 변경하는 부분도 담당자 A의 API·Repository 연결 영역입니다.

```text
프론트 요청
→ 담당자 A: 인증·Trip·Game·Stadium·Place 조회
→ 담당자 A: TripInput 조합
→ 담당자 B: 이동시간 Matrix와 일정 생성
→ 담당자 A: ItineraryPlan 저장·상태 변경
→ 프론트 응답
```

## 9. 프론트엔드 협의 자료

### 여행 입력: 프론트 요청과 알고리즘 입력을 구분

프론트가 제공해야 할 사용자 입력:

- 선택한 `gameId`
- 여행 시작·종료시각(시간대 포함 ISO 8601)
- 도착지 이름·주소·좌표
- 출발지 이름·주소·좌표
- 숙소 이름·주소·좌표 또는 숙소 없음
- 선택 장소 ID와 장소별 필수 여부

프론트는 경기장 이름·좌표·경기 시작시각을 중복 전송하지 않고 `gameId`만 보내는 방식을 권장한다. 백엔드가 Game과 Stadium을 조회해 내부 `gameAnchor`를 구성해야 데이터 불일치를 막을 수 있다. `samples/algorithm/trip_input.json`은 프론트의 최종 POST Body가 아니라, 백엔드가 조회 결과를 합쳐 알고리즘에 넘기는 **내부 입력 예시**다.

지도 임의 위치 예시:

```json
{
  "name": "사용자 선택 위치",
  "address": "부산광역시 ...",
  "latitude": 35.1,
  "longitude": 129.0
}
```

임의 위치에는 TourAPI 장소 ID가 없으므로 알고리즘 입력 `GeoPoint`에는 `placeId`를 보내지 않는다. 일정 Item으로 반환될 때는 `placeId=null`이고, 화면 식별과 표시는 `name`, `address`, 좌표를 사용한다. 저장 후 개별 일정 항목 수정에는 백엔드가 별도로 생성하는 `itemId`를 사용한다.

### 선택 장소 요청

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

확인할 UI:

- 장소 선택과 선택 해제
- 필수 방문 토글
- 선택한 장소 목록
- 필수 장소 제외 시 강한 경고

현재 v0.1에서는 배열 순서가 우선순위를 의미하지 않는다. `isRequired=true`인 장소가 먼저이며, 같은 조건에서는 이동거리가 가까운 장소를 우선한다. 사용자가 순서를 직접 지정하는 기능이 필요하다면 별도의 `priority` 또는 수동 일정 편집 계약이 필요하다.

### 일정 Item 표시

| type | 화면 의미 | 권장 표시 |
| --- | --- | --- |
| `ARRIVAL_POINT` | 여행 도착지 | 도착 아이콘·고정 항목 |
| `DEPARTURE_POINT` | 여행 출발지 | 출발 아이콘·고정 항목 |
| `ACCOMMODATION` | 숙소 | 숙소 아이콘·고정 항목 |
| `PLACE` | 관광지·음식점 등 | 카테고리별 장소 카드 |
| `STADIUM` | 경기장 | 야구장 아이콘·경기시간 강조 |

프론트와 결정할 사항:

- 유형별 아이콘과 카드 모양
- 날짜별 탭 또는 연속 목록
- 이전 Item에서 현재 Item까지의 이동시간 표시
- 필수 장소 배지
- 숙소·경기장 등 Anchor의 삭제·이동 허용 여부
- `dayType`을 사용자에게 직접 노출할지, 화면 구성에만 사용할지

### 추정 이동시간 표시

제안 필드:

```json
{
  "travelMinutesFromPrevious": 25,
  "travelTimeSource": "ODSAY"
}
```

후보 값:

- `ODSAY`: 실제 ODsay 대중교통 응답
- `ESTIMATED`: 외부 API 실패 후 직선거리 기반 추정값
- `FAKE`: 개발·Mock 전용이며 운영 응답에는 사용하지 않는 값

현재 모델에는 `travelTimeSource`가 없다. 프론트가 추정시간을 별도로 표시할 필요가 없다면 필드를 추가하지 않아도 되지만, 사용자 신뢰를 위해 `ESTIMATED`는 구분 표시하는 방안을 권장한다.

### 이미지와 운영시간 fallback

```json
{
  "thumbnailUrl": null,
  "openTime": null,
  "closeTime": null
}
```

- `thumbnailUrl=null`: 프론트 공통 placeholder 이미지 표시
- 운영시간이 `null`: `운영시간 확인 필요` 표시
- 운영시간이 없다는 이유로 `24시간 영업`이라고 표시하지 않음
- `closedDaysText`는 TourAPI 원문일 수 있으므로 표시 방식 검토

### 제외 장소

현재 코드:

- `INSUFFICIENT_TIME`
- `OUTSIDE_BUSINESS_HOURS`
- `CLOSED_DAY`
- `ROUTE_INEFFICIENT`
- `DUPLICATE_PLACE`
- `INVALID_PLACE`

프론트와 결정할 사항:

- 제외 장소를 일정 아래에 별도 목록으로 보여줄지
- 필수 장소가 제외되면 경고창 또는 상단 배너를 표시할지
- 다른 날짜로 직접 이동시키는 기능을 제공할지
- 필수 장소 제외를 전체 생성 실패로 볼지

권장안은 생성 가능한 일정은 반환하고, 필수 장소 제외를 강한 경고로 표시하는 방식이다. 이후 사용자가 조건을 수정하거나 장소를 교체할 수 있게 한다.

### 일정 수정

필드 동결 전에 범위를 결정한다.

- 개별 Item 시간 수정
- 장소 삭제·교체
- 드래그 앤 드롭 순서 변경
- 수정 후 전체 재생성
- 이전 Plan 보관 및 복원 여부

알고리즘 결과에는 `itemId`가 없으며, Firestore 저장 시 백엔드가 생성한다. 저장된 일정의 개별 Item 수정 API는 이 `itemId`를 사용한다.

### API 최종 확인

| API | 상태 | 프론트 용도 |
| --- | --- | --- |
| `GET /api/v1/games` | 구현, Firebase 필요 | 경기 선택 목록 |
| `GET /api/v1/games/{gameId}` | 구현, Firebase 필요 | 경기 상세 |
| `POST /api/v1/trips` | 구현, Firebase 필요 | 여행 기본정보 저장 |
| `GET /api/v1/tour/nearby` | 구현 | 주변 장소 목록 |
| `GET /api/v1/tour/places/{placeId}` | 구현 | 장소 상세 |
| `POST /api/v1/trips/{tripId}/itineraries` | 연결 예정 | 일정 생성·저장 |

가장 먼저 확정할 항목:

1. `travelTimeSource` 추가 및 표시 여부
2. 지도 임의 위치의 요청 형식
3. 이미지·운영시간 `null` 처리
4. 필수 장소를 포함한 제외 장소 UI
5. 일정 수정 범위와 `itemId` 사용 방식
6. Anchor Item의 삭제·이동 허용 여부

### 회의에서 보여줄 Mock 파일

| 파일 | 누구에게 보여주는가 | 설명 |
| --- | --- | --- |
| `samples/tour_api/location_based_list.json` | 백엔드·프론트 | TourAPI 원본이 어떤 형태인지 설명 |
| `samples/algorithm/places.json` | 백엔드·알고리즘 | 원본이 내부 `Place` 후보 목록으로 변환된 모습 |
| `samples/algorithm/trip_input.json` | 백엔드 공동 | 담당자 A가 데이터를 조합해 알고리즘에 넘기는 내부 입력 |
| `samples/algorithm/generated_itinerary_week2.json` | 프론트 | 현재 v0.1이 생성한 날짜별 일정 결과 |
| `samples/algorithm/itinerary_result.json` | 프론트·명세 검토 | 합의용 응답 계약 예시 |
| `samples/firestore/games.json` | Firebase 시연 대체 | 개발 경기 문서 구조 |
| `samples/firestore/stadiums.json` | Firebase 시연 대체 | 구장 문서와 좌표 구조 |

추천 순서는 `location_based_list.json → places.json → trip_input.json → generated_itinerary_week2.json`이다. 이를 통해 **외부 원본 → 내부 장소 → 알고리즘 입력 → 일정 결과** 흐름을 한 번에 설명할 수 있다. `itinerary_result.json`은 실제 최신 실행 결과라기보다 프론트와 필드명을 검토하는 계약 샘플로 구분해서 설명한다.

# 3주차 담당자 B 회의 설명 및 시연

## 한 문장 요약

이번 주에는 지난주의 단순 Anchor 기반 일정 생성기를 다일정 장소 선별,
Greedy Insertion, 2-opt, 현실적인 시간 제약, 빈 시간 자동 추천까지 가능한
`auto-fill-v0.4` 알고리즘으로 확장했다.

## 지난주 이후 변경 흐름

### 1. Kakao Local API 장소 정보 보충

- TourAPI 상세 장소의 주소가 비어 있거나 전화번호가 없거나 내부 카테고리가
  `OTHER`이면 Kakao Local REST API의 키워드 장소 검색으로 부족한 정보를
  보충한다.
- 이름의 공백·특수문자를 제거한 결과가 포함 관계이고 두 API의 좌표가 200m
  이내인 경우에만 같은 장소로 판단한다. 이름만 같은 먼 장소는 병합하지 않는다.
- TourAPI에 이미 있는 값은 덮어쓰지 않고 빈 주소·전화번호만 채우며,
  카테고리도 `OTHER`일 때만 Kakao 분류로 보충한다.
- `placeId`, `source`, `sourceContentId`는 TourAPI 값을 유지한다.
- 일치한 Kakao 장소는 `kakaoPlaceId`와 `enrichedBy: ["KAKAO"]`로 기록한다.
- Kakao 실패·빈 결과·일치 후보 없음은 TourAPI 상세 조회 전체 실패로 만들지
  않고 원본 Place를 반환한다.
- 주변 목록 전체가 아니라 `GET /api/v1/tour/places/{placeId}` 상세 조회 시에만
  호출하여 외부 호출량과 응답 지연을 줄였다.
- 대표 이미지·소개·운영시간·휴무일은 Kakao Local API가 보장하지 않으므로
  임의로 보충하지 않는다.

### 2. Place 모델 TourAPI 신분류 체계 적용

- 사용하지 않는 기존 `areaCode`, `sigunguCode`, `cat1`, `cat2`, `cat3`를
  내부 `Place` 모델과 API 응답에서 제거했다.
- TourAPI 원본의 `lclsSystm1`, `lclsSystm2`, `lclsSystm3`를 읽고 내부에서는
  철자를 정리한 `lclsSystem1`, `lclsSystem2`, `lclsSystem3`으로 반환한다.
- 신분류를 기존 `contentTypeId`보다 우선해 내부 카테고리를 결정한다.
  - `FD05...` → `CAFE`
  - 그 외 `FD...` → `RESTAURANT`
  - `AC...` → `ACCOMMODATION`
- 신분류가 없는 응답만 `contentTypeId`를 대분류 fallback으로 사용한다.
- 신분류 원본 코드는 향후 카페·음식점 세부 종류 필터와 화면 표시에 사용할 수
  있도록 Place에 보존하고, 알고리즘은 단순화된 내부 `category`를 사용한다.

### 3. 이동시간 현실화

- ODsay 대중교통 시간과 도보 예상시간을 비교해 더 빠른 수단을 사용한다.
- ODsay 실패 시 직선거리·우회계수·평균 보행속도 기반 도보시간으로 fallback한다.
- 모든 이동 구간에 실제 이동시간과 별도로 환승·대기 여유 15분을 둔다.
- API 응답에서 `travelMinutesFromPrevious`, `transferBufferMinutes`,
  `travelMode`, `travelTimeSource`를 구분한다.

### 4. 숙소와 Anchor 정책

- 경기 시작 40분 전 경기장 도착과 출발 1시간 전 도착 조건을 유지한다.
- 경기장에는 40분 외 별도 추가 완충시간을 더하지 않는다.
- 자동 생성 시 숙소는 하루 마지막 Item이며 도착 후 짐 정리 시간 30분을 둔다.
- 경기 종료 후 숙소로 돌아가는 구간에는 자동 추천을 넣지 않는다.

### 5. TourAPI 영업시간 정확화

- 요일별 영업시간과 반복 휴무일을 안전하게 해석한 경우 알고리즘에 반영한다.
- `입장 마감 17:00`, `매표 마감 오후 5시`처럼 명시적인 시각을 영업 종료와
  분리해 검증한다.
- 정보가 없거나 복잡해서 확실히 해석할 수 없으면 원문을 보존하고 알고리즘이
  임의로 휴무·24시간 영업으로 판단하지 않는다.

### 6. 경로 최적화 v0.2

- 필수 장소를 일반 장소보다 먼저 처리한다.
- 각 장소를 기존 경로의 모든 위치에 넣어 추가 이동시간이 가장 작은 위치를
  찾는 Greedy Insertion을 구현했다.
- 생성된 경로는 2-opt로 구간을 뒤집어 이동시간을 줄인다.
- 순서를 바꾼 뒤 영업시간이나 Anchor 조건을 위반하면 개선안을 채택하지 않는다.

### 7. 다일정 장소 선별 v0.3

- 장소를 첫날부터 소비하지 않고 여행 전체 날짜와 모든 삽입 위치를 비교한다.
- 날짜 Anchor 적합도, 추가 이동시간, 영업 종료 여유, Anchor 도착 여유를
  기준으로 가장 적합한 날짜에 배정한다.
- 입력 장소 순서가 달라도 같은 결과를 반환하도록 동점 기준을 고정했다.
- 제외 사유를 `CLOSED_DAY`, `ADMISSION_DEADLINE`,
  `OUTSIDE_BUSINESS_HOURS`, `ANCHOR_CONFLICT`, `INSUFFICIENT_TIME` 등으로
  구분했다.
- 필수 장소가 불가능하면 가능한 일정은 반환하되
  `hasRequiredPlaceConflict=true`로 표시한다.

### 8. 여행 후보와 개인 찜 컬렉션 정책

- 구단별 컬렉션은 제외하고 개인 찜 컬렉션만 사용한다.
- 일정에 컬렉션을 불러오면 해당 경기·경기장 지역과 일치하는 TourAPI 장소만
  자동으로 여행 후보에 포함한다.
- 컬렉션에서 불러오기, 초기 주변 추천에서 선택, 홈·지도에서 직접 추가는 모두
  동일한 여행 후보다.
- 알고리즘 입력은 `selectedPlaces[{placeId, isRequired}]`만 사용한다.
- 필수 방문 `isRequired`와 생성 후 일정 고정 `isFixed`를 분리했다.
- 홈·지도에서 장소를 누르면 여행 후보, 찜 컬렉션, 둘 다 추가 중 선택하는
  흐름으로 정리했다.
- Kakao 검색 결과는 찜이나 코스 장소로 직접 사용하지 않고, TourAPI 상세정보의
  주소·전화번호·카테고리 보충에만 사용한다.

### 9. 빈 시간 자동 추천 v0.4

- 필수 사용자 후보와 일반 사용자 후보를 먼저 배정한다.
- 그 뒤 전달받은 추천 후보로 빈 시간을 반복해서 채운다.
- 선택 장소가 없는 날도 추천 후보만으로 코스를 만들 수 있다.
- 추천 개수 상한은 두지 않고 시간·영업·동선 제약으로 제한한다.
- 추천 삽입은 추가 이동시간 30분 이하이고 삽입 후 최소 30분 여유가 남아야 한다.
- 숙박은 추천하지 않고 축제는 운영일을 확인할 수 있을 때만 추천한다.
- 사용자 장소는 `addedBy=USER`, 자동 추천은 `addedBy=ALGORITHM`,
  Anchor는 `addedBy=null`이다.
- 결과에 `autoFillApplied`와 `autoRecommendedPlaceCount`를 반환한다.

### 10. 카테고리별 체류시간

| 카테고리 | 기본 체류시간 |
| --- | ---: |
| 카페 | 45분 |
| 음식점 | 60분 |
| 관광지 | 90분 |
| 문화시설 | 90분 |
| 쇼핑 | 60분 |
| 액티비티 | 120분 |
| 축제 | 120분 |
| 기타 | 60분 |

TourAPI 장소를 내부 `Place`로 변환할 때 이 기본값을 설정한다.

## 회의 발표 대본

> 지난주에는 TourAPI 장소와 이동시간 Matrix를 받아 Anchor 중심으로 날짜별
> 일정을 만드는 기본 버전까지 구현했습니다. 이번 주에는 실제 여행 일정으로
> 사용할 수 있도록 장소 선별과 경로 최적화를 고도화했습니다.
>
> 그 전에 장소 데이터 품질도 보완했습니다. TourAPI 상세정보에서 주소나
> 전화번호가 부족하면 Kakao Local API로 같은 장소를 찾아 빈 값만 채웁니다.
> 이름과 좌표 200m 조건을 모두 만족해야 병합하고, 실패해도 TourAPI 원본은
> 그대로 반환합니다.
>
> TourAPI 분류도 기존 cat1·cat2·cat3 대신 새로 제공되는 lclsSystm1·2·3을
> 내부 Place의 lclsSystem1·2·3으로 변환했습니다. 이를 이용해 카페와 음식점,
> 숙박을 더 세밀하게 구분하고 신분류가 없을 때만 contentTypeId를 사용합니다.
>
> 먼저 사용자가 꼭 가고 싶은 필수 장소를 일반 장소보다 먼저 처리합니다.
> 장소마다 여행 전체 날짜와 가능한 모든 삽입 위치를 확인하기 때문에 첫날에
> 영업하지 않는 장소도 바로 제외하지 않고 다른 영업일에 배정할 수 있습니다.
>
> 날짜별 순서는 Greedy Insertion으로 추가 이동시간이 가장 작은 위치에 넣고,
> 이후 2-opt로 불필요한 왕복 동선을 줄입니다. 다만 영업시간이나 경기장 40분 전
> 도착 조건을 위반하는 순서 변경은 적용하지 않습니다.
>
> 시간 계산에는 실제 이동시간 외에 구간마다 환승과 대기를 위한 15분을 따로
> 확보했습니다. 숙소는 기본적으로 하루 마지막에 배치하고 30분 체류로 계산합니다.
> TourAPI에 명시적인 입장 마감 정보가 있으면 그 시각도 일정 제약으로 사용합니다.
>
> 사용자가 선택한 장소만으로 빈 시간이 생기면 추천 후보를 자동으로 넣습니다.
> 자동 추천은 사용자 장소를 밀어내지 않고, 추가 이동시간 30분 이하와 추천 후
> 최소 30분 여유를 모두 만족할 때만 삽입합니다. 결과에서는 사용자 장소와 자동
> 추천 장소를 `addedBy`로 구분합니다.
>
> 현재 순수 알고리즘과 Mock 데이터 검증까지 완료했고 전체 테스트 157개가
> 통과했습니다. 실제 추천 후보 조회, Firestore 저장, 일정 편집과 고정 기반
> 재생성은 Application Service와 수정 API가 필요해서 다음 주차로 이관했습니다.

## 시연 순서

### 1. 테스트 전체 통과

```powershell
uv run pytest -q
```

기대 결과:

```text
157 passed
```

### 2. Place 신분류 변환 확인

```powershell
uv run pytest -q tests/test_place_mapper.py
```

확인할 내용:

- TourAPI `lclsSystm1/2/3`이 내부 `lclsSystem1/2/3`으로 변환
- `FD05`가 `CAFE`로 매핑
- 기존 `areaCode`, `sigunguCode`, `categoryCode1~3`는 Place 응답에 없음
- 카페 기본 체류시간 45분 적용

### 3. Kakao 정보 보충 확인

```powershell
uv run pytest -q tests/test_kakao_place_enrichment.py
```

확인할 내용:

- 빈 주소·전화번호·`OTHER` 카테고리만 보충
- 200m 밖의 동명 장소는 병합하지 않음
- 성공 시 `kakaoPlaceId`, `enrichedBy` 기록
- Kakao 실패 시 TourAPI 원본 Place 유지

실제 키가 설정된 서버에서는 다음 상세 조회를 호출한다.

```http
GET /api/v1/tour/places/tour_1603175
```

응답의 `kakaoPlaceId`와 `enrichedBy`가 채워졌다면 Kakao 보충이 적용된 것이다.
TourAPI 원본 정보가 이미 충분하면 두 필드가 비어 있어도 정상이다.

### 4. 사용자 장소만으로 생성

```powershell
uv run python -m scripts.demo_itinerary
```

확인할 필드:

- `algorithmVersion: auto-fill-v0.4`
- 사용자 장소 `addedBy: USER`
- Anchor `addedBy: null`
- `autoFillApplied: false`
- `transferBufferMinutes: 15`

### 5. 빈 시간 자동 추천 시연

```powershell
uv run python -m scripts.demo_itinerary --auto-fill
```

확인할 흐름:

- 도착일: 사용자 선택 광안리해수욕장 뒤에 추천 카페 배정
- 경기일: 경기장 방문 전에 추천 음식점 배정
- 출발일: 출발지 이동 전에 추천 문화시설 배정
- 자동 추천 세 곳 모두 `addedBy: ALGORITHM`
- `autoFillApplied: true`
- `autoRecommendedPlaceCount: 3`
- 경기장은 정확히 경기 시작 40분 전에 배치
- 경기 종료 후에는 숙소만 배치

## 시연 자료 순서

1. `samples/tour_api/location_based_list.json`: 신분류가 포함된 TourAPI 원본
2. `samples/algorithm/trip_input.json`: 여행·Anchor·사용자 후보 입력
3. `samples/algorithm/places.json`: 사용자가 선택한 내부 Place
4. `samples/algorithm/recommended_places.json`: 빈 시간용 추천 후보
5. `samples/algorithm/auto_filled_itinerary.json`: 자동 추천이 적용된 결과

## 다음 주차 이관

- 실제 TourAPI·저장 Place에서 추천 후보를 만드는 서비스
- 여행 후보·찜 컬렉션 CRUD
- 일정 생성 API와 Firestore Plan 저장
- 일정 Item 편집 및 수동 추가 후 시간표 재계산
- 숙소 중간 이동 처리
- `isFixed` 기반 부분 재최적화와 재생성
- 실데이터 통합 테스트와 성능 제한

이번 회의에서는 위 항목을 미완성으로 숨기지 않고, 순수 알고리즘 계약과 Mock
검증까지가 이번 주 완료 범위이며 실제 서비스 연결은 다음 주차 작업이라고 설명한다.

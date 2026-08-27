# 자동 추천 진단 필드

일정 생성 응답의 `recommendationSummary`는 자동 추천 후보가 어떻게 준비되고
배치되었는지 요약한다. 프론트의 일반 일정 화면보다는 개발·운영 검증과 추천 품질
분석에 사용하는 필드다.

## 개수 필드

- `fetchedCount`: 경기장과 도착지 주변 TourAPI에서 받은 항목 수. 기준점 사이의
  중복도 제거하기 전이므로 실제 고유 장소 수보다 클 수 있다.
- `candidateCount`: 출처, 중복, 숙박, 체육시설, 카테고리 상한, 축제 기간 등을
  적용하고 상세정보 확인까지 마친 최종 후보 수다.
- `scheduledCount`: 최종 일정에 실제로 삽입된 자동 추천 장소 수다.
- `scheduledByDay`: 날짜별 자동 추천 삽입 수다. 도착일·출발일에 후보가 먼저
  소진되지 않도록 가능한 날짜를 순환해 배치했는지 확인한다.
- `categoryDistribution`: 최종 후보의 내부 `PlaceCategory`별 개수다.
- `sourceCategoryDistribution`: 중복·출처·Anchor 필터 후 원천 후보의 카테고리
  분포다. 특정 지역에서 TourAPI 자체에 쇼핑 등이 없는지를 구분할 수 있다.
- `missingSourceCategories`: 원천 후보에 존재하지 않는 주요 카테고리 목록이다.
  이 값에 포함된 카테고리는 백엔드가 임의의 장소로 채우지 않는다.
- `businessHoursStatusDistribution`: 최종 후보의 `PARSED`, `MISSING`,
  `UNPARSABLE`, `COMPLEX` 분포다. `PARSED`만 시간 제약에 사용하고 나머지는
  원문 또는 `운영시간 확인 필요`로 표시한다.
- `detailLookupCount`: 이번 후보 준비에서 상세 조회 대상으로 정한 장소 수다.
  실제 TourAPI HTTP 호출 수는 대표 이미지 존재 여부 등에 따라 달라질 수 있다.

## `filteredCounts`

후보 준비 단계에서 제외된 항목 수다. 한 항목은 처음 일치한 사유 하나로 센다.

- `ALREADY_SELECTED_OR_REJECTED`: 사용자 후보이거나 이전 재생성에서 거부됨
- `ANCHOR_DUPLICATE`: 경기장과 이름 또는 좌표가 사실상 같음
- `UNSUPPORTED_SOURCE`: TourAPI 장소가 아님
- `ACCOMMODATION`: 숙박은 자동 추천 대상이 아님
- `SPORTS_FACILITY`: 신분류 `VE10` 경기·체육시설
- `DUPLICATE_PLACE`: 같은 `placeId` 중복
- `CATEGORY_LIMIT_RELAXED`: 지역 원천 카테고리가 부족해 soft cap을 완화하고
  다른 카테고리로 후보 수를 보충함
- `CANDIDATE_LIMIT`: 전체 후보 최대 개수 초과
- `UNVERIFIED_FESTIVAL`: 운영정보를 안전하게 확인할 수 없는 축제
- `OUTSIDE_EVENT_PERIOD`: 여행 기간과 행사 기간이 겹치지 않는 축제
- `RECOMMENDATION_TIMEOUT`: 후보 준비가 제한시간을 초과함

## `placementRejectedAttempts`

일정 배치 단계에서 실패한 **삽입 시도 횟수**다. 장소 고유 개수가 아니다. 같은
장소를 여러 날짜와 여러 순서에 넣어보면 실패 횟수가 여러 번 증가할 수 있다.

- `INSUFFICIENT_TIME`: 체류·이동·여유시간을 확보할 수 없음
- `OUTSIDE_BUSINESS_HOURS`: 방문 시간이 영업시간 밖임
- `CLOSED_DAY`: 해당 날짜가 휴무일임
- `ROUTE_INEFFICIENT`: 추가 우회시간이 허용 범위를 초과함
- `UNVERIFIED_FESTIVAL`: 운영 조건을 안전하게 확인할 수 없는 축제
- `INVALID_PLACE`: 장소 정보가 일정 계산에 부족함

## `excludedPlaces`와의 차이

`excludedPlaces`는 사용자가 선택한 특정 장소가 일정에 들어가지 못했을 때
`placeId`, 필수 여부와 대표 사유를 제공한다. `recommendationSummary`는 자동 추천
전체 과정의 집계다. 자동 추천 후보별 상세 실패 목록은 응답 크기와 내부 구현 노출을
막기 위해 제공하지 않는다.

## 응답 예시

```json
{
  "recommendationSummary": {
    "fetchedCount": 40,
    "candidateCount": 12,
    "scheduledCount": 3,
    "scheduledByDay": {
      "2026-08-15": 1,
      "2026-08-16": 1,
      "2026-08-17": 1
    },
    "categoryDistribution": {
      "CAFE": 2,
      "RESTAURANT": 4,
      "TOURIST_SPOT": 4
    },
    "missingSourceCategories": ["SHOPPING"],
    "businessHoursStatusDistribution": {
      "MISSING": 3,
      "PARSED": 9
    },
    "detailLookupCount": 12,
    "filteredCounts": {
      "ACCOMMODATION": 3,
      "SPORTS_FACILITY": 1
    },
    "placementRejectedAttempts": {
      "INSUFFICIENT_TIME": 8,
      "ROUTE_INEFFICIENT": 4
    }
  }
}
```

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
- `categoryDistribution`: 최종 후보의 내부 `PlaceCategory`별 개수다.

## `filteredCounts`

후보 준비 단계에서 제외된 항목 수다. 한 항목은 처음 일치한 사유 하나로 센다.

- `ALREADY_SELECTED_OR_REJECTED`: 사용자 후보이거나 이전 재생성에서 거부됨
- `ANCHOR_DUPLICATE`: 경기장과 이름 또는 좌표가 사실상 같음
- `UNSUPPORTED_SOURCE`: TourAPI 장소가 아님
- `ACCOMMODATION`: 숙박은 자동 추천 대상이 아님
- `SPORTS_FACILITY`: 신분류 `VE10` 경기·체육시설
- `DUPLICATE_PLACE`: 같은 `placeId` 중복
- `CATEGORY_LIMIT`: 음식점·카페·쇼핑·축제 카테고리 상한 초과
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
    "categoryDistribution": {
      "CAFE": 2,
      "RESTAURANT": 4,
      "TOURIST_SPOT": 4
    },
    "filteredCounts": {
      "ACCOMMODATION": 3,
      "CATEGORY_LIMIT": 6,
      "SPORTS_FACILITY": 1
    },
    "placementRejectedAttempts": {
      "INSUFFICIENT_TIME": 8,
      "ROUTE_INEFFICIENT": 4
    }
  }
}
```

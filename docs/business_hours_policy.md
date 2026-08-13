# 영업시간·휴무일 파싱 정책

TourAPI의 콘텐츠 유형별 운영시간과 휴무일 원문은 항상 보존한다. 알고리즘은
안전하게 해석된 규칙만 사용하고, 불확실한 정보는 사용자에게 원문으로 보여준다.

## API 필드

- `businessHoursText`: 운영시간 원문
- `businessHoursStatus`: `PARSED`, `MISSING`, `UNPARSABLE`, `COMPLEX`
- `businessHoursRules`: 요일별 `weekdays`, `openTime`, `closeTime`
- `admissionDeadlineTime`: 안전하게 해석한 입장·매표 마감 시각
- `admissionDeadlineStatus`: 입장 마감 파싱 상태
- `admissionDeadlineText`: 입장 마감이 포함된 TourAPI 원문
- `closedDaysText`: 휴무일 원문
- `closedDaysStatus`: 휴무일 파싱 상태
- `closedWeekdays`: 매주 반복되는 휴무 요일

`openTime`, `closeTime`은 모든 요일에 동일한 단일 규칙일 때의 호환 필드다.
요일별 시간이 다르면 두 필드는 `null`이고 `businessHoursRules`를 사용한다.

## 현재 안전하게 처리하는 표현

- `09:00~18:00`, `매일 오전 9시~오후 6시`
- `평일 09:00~18:00 / 주말 10:00~17:00`
- `월~금 09:00~18:00 / 토~일 10:00~17:00`
- `24시간`, `상시 개방`
- `매주 월요일`, `토요일, 일요일`, `연중무휴`

공휴일·계절·월의 몇 번째 요일·브레이크타임·자정 이후 영업 등은
`COMPLEX`로 보존한다. 원문은 API로 반환하지만 알고리즘 제약에는 적용하지 않는다.
프론트는 `PARSED`가 아니면 원문과 함께 `방문 전 운영시간 확인 필요`를 표시한다.

`입장 마감 17:00`, `매표 마감 오후 5시`처럼 명시적인 시각이 하나인 경우에는
영업시간과 분리하여 `admissionDeadlineTime`으로 변환한다. 알고리즘은 방문 시작
시각이 이 시각을 넘지 않게 검증한다. 표현이 없거나 안전하게 해석할 수 없으면
마감시각을 추정하지 않고 `MISSING` 또는 `COMPLEX`로 반환하여 사용자가 확인하게 한다.

일정 생성기는 방문 날짜의 요일에 해당하는 영업 규칙만 적용하고,
`closedDaysStatus=PARSED`일 때만 해당 요일을 휴무로 판단한다.

# Week 3 합의 정책

## 여행 입력

- 프론트는 `gameId`, 여행 시작·종료시각, 도착지·출발지, 숙소, 선택 장소와 필수 여부를 전달한다.
- 경기장 이름·좌표·경기 시작시각은 프론트가 중복 전송하지 않는다.
- 백엔드가 `gameId`로 Game과 Stadium을 조회해 알고리즘의 `gameAnchor`를 구성한다.
- `samples/algorithm/trip_input.json`은 프론트 요청 Body가 아니라 백엔드가 조합한 내부 알고리즘 입력 예시다.
- 지도에서 임의 위치를 선택하는 기능은 현재 범위에서 제외한다.

## 선택 장소

- 요청 형식은 `selectedPlaces[{placeId, isRequired}]`를 사용한다.
- 배열 순서는 우선순위를 의미하지 않는다.
- 필수 장소를 먼저 고려하고 같은 조건에서는 이동시간이 짧은 장소를 우선한다.

## 이동시간

- `travelMinutesFromPrevious`와 함께 `travelMode`, `travelTimeSource`를 API에 항상 포함한다.
- 도보 예상시간과 ODsay 대중교통 최단시간을 비교해 더 빠른 수단을 선택한다.
- 도보시간은 실제 보행 경로 API가 연결되기 전까지 직선거리, 우회계수, 평균 보행속도로 추정한다.
- `travelMode`: `WALK`, `TRANSIT`
- `travelTimeSource`: `ODSAY`, `ESTIMATED`, `FAKE`
- `FAKE`는 테스트와 Mock에서만 사용한다.

## 이미지·운영시간

- `thumbnailUrl=null`이면 프론트가 공통 placeholder를 표시한다.
- `openTime` 또는 `closeTime`이 없으면 `운영시간 확인 필요`로 표시한다.
- 운영시간이 없다는 이유로 24시간 영업으로 표시하지 않는다.

## 제외 장소

- 별도의 제외 장소 UI, 필수 장소 경고창, 전체 생성 실패 처리는 현재 프론트 범위에서 제외한다.
- 알고리즘의 검증과 기록을 위해 `excludedPlaces`와 제외 사유 코드는 API 결과에 유지한다.

## 일정 표시와 편집

- Item type은 `ARRIVAL_POINT`, `DEPARTURE_POINT`, `ACCOMMODATION`, `PLACE`, `STADIUM`을 사용한다.
- 개별 Item 시간 수정, 장소 삭제·교체, 드래그 앤 드롭 순서 변경, 수정 후 전체 재생성을 지원하는 방향으로 구현한다.
- 알고리즘 결과에는 `itemId`가 없고 Firestore 저장 시 백엔드가 생성한다.
- 저장된 일정의 수정 API는 `itemId`를 사용한다.

## Anchor 정책

| Anchor | 삭제 | 시간·위치 변경 |
| --- | --- | --- |
| 도착지 | 불가 | 여행 입력 수정 후 재생성 |
| 출발지 | 불가 | 여행 입력 수정 후 재생성 |
| 경기장 | 불가 | 경기 변경 후 재생성 |
| 숙소 | 가능 | 숙소 변경 후 재생성 |

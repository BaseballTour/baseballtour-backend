# Kakao 숙소 Anchor 설계

## 목적과 범위

TourAPI에 등록되지 않은 숙소도 사용자가 일정의 숙소 Anchor로 선택할 수 있도록
Kakao Local API를 사용한다. Kakao 숙소는 관광지 자동 추천, 일반 장소 후보,
찜 컬렉션에는 넣지 않고 여행의 `accommodation`에만 사용한다.

## 사용자 흐름

1. 프론트가 숙소 이름을 검색하거나 지도에서 좌표를 선택한다.
2. 백엔드가 Kakao Local 결과를 `AccommodationCandidate`로 정규화한다.
3. 사용자가 숙소 후보를 선택한다.
4. 프론트가 선택한 후보 정보를 `POST /api/v1/trips` 또는 여행 수정 요청의
   `accommodation`에 담는다.
5. 기존 일정 생성기가 이를 `type=ACCOMMODATION` Anchor로 사용한다.

## 숙박업소 검색

```http
GET /api/v1/accommodations/search?keyword=잠실 호텔&longitude=127.076&latitude=37.510
```

- Kakao 카테고리 그룹 `AD5`를 강제하여 숙박업소만 조회한다.
- 좌표를 보낼 때는 경도와 위도를 함께 보내야 한다.
- `pageToken`과 `pageSize`로 다음 페이지를 조회할 수 있으며 `pageSize`의 기본값과
  최대값은 모두 15다.
- 응답의 `kakaoPlaceId`는 외부 출처 식별자이며 일반 `placeId`가 아니다.

## 지도 좌표 선택

```http
GET /api/v1/accommodations/reverse-geocode?longitude=129.0756&latitude=35.1796
```

지도에서 선택한 좌표를 Kakao 주소로 변환한다. 특정 Kakao 장소를 선택한 것이
아니므로 `selectionType=MAP_POINT`, `kakaoPlaceId=null`이다. 주소 검색이 실패하면
`ACCOMMODATION_ADDRESS_NOT_FOUND`를 반환한다.

## 여행 생성 요청 예시

숙소 선택은 별도 저장 요청이 아니라 경기와 여행 시간, 도착·출발 지점을 담는
여행 생성 요청에 함께 포함한다. 프론트는 경기 시간과 경기장 정보를 중복해서
보내지 않고 `gameId`만 보내며, 백엔드가 Game과 Stadium을 조회한다.

```json
{
  "gameId": "game_20260922_lg_doosan",
  "title": "잠실 원정 1박 2일",
  "tripStartAt": "2026-09-22T12:00:00+09:00",
  "tripEndAt": "2026-09-23T19:00:00+09:00",
  "arrivalPoint": {
    "name": "서울역",
    "latitude": 37.5547,
    "longitude": 126.9706
  },
  "departurePoint": {
    "name": "서울역",
    "latitude": 37.5547,
    "longitude": 126.9706
  },
  "accommodation": {
    "kakaoPlaceId": "123456789",
    "name": "잠실 예시 호텔",
    "address": "서울특별시 송파구 ...",
    "latitude": 37.51,
    "longitude": 127.08
  }
}
```

- `tripStartAt`: 도착역에 도착하는 일시이자 여행 일정 시작
- `tripEndAt`: 출발역에서 출발하는 일시이자 여행 일정 종료
- `arrivalPoint`, `departurePoint`: 역 이름과 좌표
- `accommodation`: 사용자가 카카오 검색 또는 지도에서 선택한 숙소
- `gameId`: 백엔드가 경기 시작시각과 경기장을 조회하는 기준

앱은 체크인·체크아웃 시각을 입력받거나 일정 제약으로 사용하지 않는다. 지도 좌표
선택은 `kakaoPlaceId`를 생략한다.

## 일정 생성 정책

- 숙소는 `ACCOMMODATION` Anchor이며 자동 추천 장소와 구분한다.
- 기본적으로 하루의 마지막에 배치한다.
- 사용자가 숙소 Item 순서를 옮기면 30분 체류시간을 적용한다.
- 숙소 체크인·체크아웃 가능 시간은 수집하거나 검증하지 않는다.
- 일반 관광 장소 자동 추천은 계속 TourAPI 장소만 사용한다.

## 환경변수와 보안

```env
KAKAO_REST_API_KEY=
```

REST API 키는 백엔드 환경변수 또는 Secret Manager에만 저장하며 앱 응답과 Git에
노출하지 않는다. iOS 지도 표시는 KakaoMapsSDK용 네이티브 앱 키를 별도로 쓴다.

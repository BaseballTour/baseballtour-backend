# TourAPI 조사 기록

## 사용 서비스

- 서비스: 한국관광공사 국문 관광정보 서비스
- Base URL: `https://apis.data.go.kr/B551011/KorService2`
- 응답 형식: JSON (`_type=json`)
- 인증: 서버 환경변수 `TOUR_API_KEY`

API 키는 `.env`에만 저장하고 Git, 샘플 JSON, 클라이언트 응답 로그에 남기지 않는다.

## 1주차 확인 대상

| 기능 | Endpoint | 구현 함수 |
| --- | --- | --- |
| 위치 기반 조회 | `locationBasedList2` | `get_nearby_places` |
| 공통정보 조회 | `detailCommon2` | `get_place_common_info` |
| 소개정보 조회 | `detailIntro2` | `get_place_intro_info` |
| 이미지 조회 | `detailImage2` | `get_place_images` |

## 응답 및 오류

- HTTP 상태와 `response.header.resultCode`를 모두 검사한다.
- 성공 코드는 `0000`이다.
- 빈 목록은 `response.body.items`가 빈 문자열 등으로 올 수 있어 `[]`로 정규화한다.
- timeout은 `EXTERNAL_API_TIMEOUT`, 연결·HTTP 장애는
  `EXTERNAL_API_UNAVAILABLE`, 비정상 JSON은
  `EXTERNAL_API_INVALID_RESPONSE`, TourAPI 업무 오류는 `TOUR_API_FAILED`로
  변환한다.
- HTTP 429는 `EXTERNAL_API_RATE_LIMITED`로 변환한다.

## 호출 제한

공공데이터포털의 2026년 7월 확인값은 개발계정 1,000회이며, 운영계정은
활용사례 등록 후 트래픽 증설을 신청할 수 있다. 실제 계정에 표시되는 잔여량과
승인 조건을 배포 전에 다시 확인한다.

공식 명세:
<https://www.data.go.kr/data/15101578/openapi.do>

## 샘플 관리

`samples/tour_api/`에는 API 키를 제거한 고정 응답만 저장한다. 실제 호출 결과로
교체할 때도 요청 URL의 `serviceKey`와 사용자 관련 정보가 포함되지 않았는지
확인한다.

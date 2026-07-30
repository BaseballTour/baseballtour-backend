# TourAPI samples

`location_based_list.json`은 API 키와 개인정보를 제거한 위치 기반 조회 응답 예시다.
실제 호출 결과를 갱신할 때도 `serviceKey`를 파일에 저장하지 않는다.

TourAPI는 HTTP 상태가 200이어도 `response.header.resultCode`로 오류를 반환할 수
있으므로 클라이언트와 테스트에서 두 상태를 모두 확인한다.

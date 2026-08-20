# 지도·이동시간 API 결정

## 결정

- 장소·주소 보강: Kakao Local API
- 전국 대중교통·도보 이동시간: Kakao Map Routing REST API
- 외부 API 실패 또는 키 미설정: Haversine 직선거리 기반 예상시간
- 개발·단위 테스트: 가짜 `TravelTimeMatrix`

2026년 7월 공개된 Kakao Map Routing REST API의 대중교통·도보 경로를
동시에 조회하고 실제 소요시간이 짧은 수단을 사용한다. 장소 후보는 기존 합의대로
TourAPI만 사용하며 카카오는 이동시간 공급자로만 사용한다.

모든 장소 쌍을 외부 API로 조회하지 않는다. Anchor 간 경로, 일정에서 필요한
Anchor→장소·장소→Anchor 경로와 장소별 가까운 이웃 2개만 조회하며 나머지는
직선거리 기반 추정값으로 유지한다. 동일 좌표 쌍 결과는 30분 캐시한다.

```env
KAKAO_REST_API_KEY=
```

API Key는 Git에 올리지 않는다. 카카오 대중교통과 도보가 모두 실패한 경로는
Haversine 직선거리, 우회계수와 평균 보행속도로 계산한 `WALK/ESTIMATED`를
사용한다. 이 값은 알고리즘 중단을 막기 위한 추정치다.

## 실호출 검증

- Kakao Map API 활성화와 REST API Key 인증 확인
- 동일 좌표 쌍에서 대중교통·도보 응답 비교 확인
- 장소 15개·Anchor 3개 기준 Provider 경로 342개에서 최대 81개로 축소 확인
- `travelTimeSource=KAKAO` 및 실패 시 `ESTIMATED` 확인

```powershell
uv run pytest -q tests/test_kakao_routing.py tests/test_travel_time.py
```

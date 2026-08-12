# Kakao 장소 정보 보충 설계

## 역할 분리

- 백엔드: TourAPI 장소를 내부 `Place`로 변환하고 부족한 기본 정보를
  Kakao Local REST API로 보충한다.
- iOS: KakaoMapsSDK로 지도를 표시하고 백엔드가 반환한 위도·경도에 마커를
  그린다. REST API 키로 장소 보충을 직접 수행하지 않는다.

## 현재 적용 범위

`GET /api/v1/tour/places/{placeId}` 상세 조회에서 다음 중 하나가 부족하면
카카오 키워드 장소 검색을 수행한다.

- 주소가 비어 있음
- 전화번호가 없음
- 내부 카테고리가 `OTHER`

주변 목록은 호출량과 응답시간을 줄이기 위해 보충하지 않는다. 상세 화면을
열 때만 보충한다. 카카오 호출 실패·빈 결과·일치 후보 없음은 TourAPI 상세
조회의 실패로 처리하지 않고 원본 `Place`를 반환한다.

## 동일 장소 판정

이름만으로 병합하지 않는다. 현재 정책은 다음 조건을 모두 만족해야 한다.

1. 공백과 특수문자를 제거한 이름이 서로 포함 관계일 것
2. TourAPI 좌표와 Kakao 좌표 사이가 200m 이내일 것
3. 좌표가 유효한 위도·경도 범위일 것

200m는 프로젝트 초기 정책값이다. 실제 데이터 검증 후 구장·관광지·음식점별
기준을 조정할 수 있다.

## 병합 정책

- 기존 값은 덮어쓰지 않고 빈 `address`, `telephone`만 채운다.
- 카테고리는 기존 값이 `OTHER`일 때만 Kakao 카테고리로 보충한다.
- `placeId`, `source`, `sourceContentId`는 TourAPI 값을 유지한다.
- 매칭된 Kakao ID는 `kakaoPlaceId`에 기록한다.
- 실제 보충이 발생했음을 `enrichedBy: ["KAKAO"]`로 표시한다.
- 이미지, 소개, 운영시간, 휴무일은 Kakao Local 응답의 보장 필드가 아니므로
  보충하지 않고 TourAPI 값 또는 `null`을 유지한다.

카카오 단독 장소를 도입할 때는 `placeId=kakao_{id}`, `source=KAKAO`,
`sourceContentId={id}` 규칙을 사용한다. 이 기능은 현재 범위에 포함하지 않는다.

## 환경변수

```env
KAKAO_REST_API_KEY=
```

실제 키는 로컬·배포 환경의 `.env` 또는 비밀 저장소에만 두고 Git에 올리지
않는다. iOS 지도 SDK용 네이티브 앱 키와 백엔드 REST API 키는 구분한다.

### Kakao Developers 사전 설정

키 발급만으로 장소 검색이 바로 허용되지 않을 수 있다. Kakao Developers의
해당 앱에서 **카카오맵 API(지도/로컬)** 사용을 활성화해야 한다. 활성화되지
않은 앱은 다음 오류를 반환한다.

```text
403 NotAuthorizedError
App(...) disabled OPEN_MAP_AND_LOCAL service.
```

이 경우 백엔드는 `KAKAO_LOCAL_API_NOT_ENABLED`로 구분한다. 앱 설정에서
카카오맵 API를 활성화한 뒤 Kakao Developers의 REST API 테스트 도구 또는
아래 상세 조회로 다시 확인한다. REST 키에 허용 IP를 설정했다면 로컬 개발
PC와 배포 서버의 외부 IP가 허용되어 있는지도 확인한다.

## 테스트

```powershell
uv run pytest -q
uv run python -m compileall -q app
```

실제 키를 사용한 수동 확인:

```http
GET /api/v1/tour/places/tour_1603175
```

응답에서 `kakaoPlaceId`와 `enrichedBy`가 채워졌다면 Kakao 보충이 적용된
것이다. TourAPI 정보가 이미 충분하거나 일치 후보가 없으면 두 필드는 비어
있을 수 있으며 정상 동작이다.

## 현재 확인 상태 (2026-08-12)

- Mock 기반 Kakao client·매칭·병합 테스트 통과
- 전체 백엔드 테스트 통과
- 실제 REST 키 인증 요청은 앱의 카카오맵 API가 비활성화되어 `403
  NotAuthorizedError` 반환
- 카카오맵 API 활성화 후 실제 장소 보충 재검증 필요

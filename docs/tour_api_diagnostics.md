# TourAPI 장애·timeout 자가 점검

## 실행

`.env`에 `TOUR_API_KEY`를 설정한 뒤 프로젝트 루트에서 실행한다.

```powershell
uv run python -m scripts.diagnose_tour_api --repeat 3
```

주변 조회, 키워드 검색, 공통 상세, 소개, 이미지 API를 같은 HTTP 연결로
각각 세 번 호출한다. 키 값과 전체 원본 응답은 출력하지 않는다.

특정 장소를 확인하려면 다음 값을 바꾼다.

```powershell
uv run python -m scripts.diagnose_tour_api `
  --content-id 1603175 `
  --content-type-id 12 `
  --keyword 아시아공원 `
  --repeat 5
```

## 결과 해석

| 결과 | 의미 | 우선 점검 |
| --- | --- | --- |
| `ConnectTimeout` | 서버까지 연결을 만들지 못함 | Cloud Run 외부 통신, DNS, 일시 장애 |
| `ReadTimeout` | 연결 후 제한 시간 안에 응답이 끝나지 않음 | TourAPI 지연, 응답 크기, 반복 호출량 |
| `PoolTimeout` | 내부 연결 풀이 부족함 | 동시 호출 수, 클라이언트 재사용 여부 |
| `EXTERNAL_API_RATE_LIMITED` | 공공데이터 호출 한도 초과 | API 사용량과 키 할당량 |
| `TOUR_API_FAILED` | TourAPI 업무 오류 | `resultCode`, `resultMessage` |
| `EXTERNAL_API_INVALID_RESPONSE` | JSON 또는 응답 구조가 비정상 | 게이트웨이 HTML/XML 오류 여부 |
| 성공하면서 `item_count=0` | 정상적인 빈 검색 결과 | 좌표·반경·분류·검색어 |

로컬에서는 성공하지만 Cloud Run에서만 `ConnectTimeout`이면 애플리케이션
파라미터보다 배포 환경의 외부 연결을 먼저 확인한다. 양쪽 모두 같은
엔드포인트에서 `ReadTimeout`이면 TourAPI 자체 지연 가능성이 높다.

## 운영 설정

기본값은 연결 5초, 응답 10초, 최대 2회 시도, 재시도 전 0.25초 대기다.
`ConnectTimeout`과 `ReadTimeout`에만 재시도하며 인증 오류, 호출 제한,
잘못된 요청은 재시도하지 않는다.

```dotenv
TOUR_API_CONNECT_TIMEOUT_SECONDS=5
TOUR_API_READ_TIMEOUT_SECONDS=10
TOUR_API_WRITE_TIMEOUT_SECONDS=5
TOUR_API_POOL_TIMEOUT_SECONDS=5
TOUR_API_MAX_ATTEMPTS=2
TOUR_API_RETRY_BACKOFF_SECONDS=0.25
```

Cloud Run 로그에서는 다음 필드를 확인한다.

```text
endpoint, timeout_type, attempt, max_attempts, elapsed_ms
```

상세 조회가 지연되면 주변 조회 장소를 사용해 일정 생성을 계속한다.
주변 조회가 반복 실패하면 추천만 생략하며, 사용자가 선택한 장소로 만들 수
있는 일정까지 외부 API 장애 때문에 실패시키지 않는다.

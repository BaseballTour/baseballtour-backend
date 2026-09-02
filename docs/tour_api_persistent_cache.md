# TourAPI 공유 응답 캐시

## 목적

같은 TourAPI 응답을 Cloud Run 인스턴스마다 다시 요청하지 않도록 메모리 캐시와
Firestore 공유 캐시를 함께 사용한다. 메모리 캐시는 같은 인스턴스의 반복 요청을,
Firestore 캐시는 새 인스턴스·재배포 이후의 반복 요청을 줄인다.

## 저장 구조

컬렉션은 `tourApiResponseCache`이며 문서 ID는 엔드포인트와 요청 파라미터를
정규화한 SHA-256 값이다. 실제 API 키는 문서 ID나 필드에 저장하지 않는다.

```text
tourApiResponseCache/{cacheKey}
  endpoint
  payload
  createdAt
  expiresAt
```

| 응답 | 유효시간 |
| --- | ---: |
| 위치 기반·키워드 검색 | 30분 |
| 신분류 코드 | 24시간 |
| 공통·소개·이미지 상세 | 12시간 |

캐시 조회·저장에 실패해도 TourAPI 호출은 계속한다. TourAPI 정상 응답만 저장하며
timeout, 인증 오류, 호출 제한, 비정상 응답은 캐시하지 않는다.

## 운영 설정

```dotenv
TOUR_API_PERSISTENT_CACHE_ENABLED=true
```

Firestore에서 `expiresAt` 필드에 TTL 정책을 설정하면 만료 문서를 자동 정리할 수
있다. TTL 삭제가 다소 늦어져도 애플리케이션이 만료시각을 직접 검사하므로 오래된
응답이 반환되지는 않는다.

Cloud Run 로그에서 다음 메시지로 동작을 확인한다.

```text
TourAPI persistent cache hit
TourAPI persistent cache miss
TourAPI persistent cache stored
TourAPI persistent cache read failed
TourAPI persistent cache write failed
```

로컬 Firestore 연결 검증에서는 위치·공통·소개·이미지 응답 4건이 저장됐고 API
키 필드는 저장되지 않았다. 새 프로세스의 상세 조회는 약 187~219ms에서
16~31ms로 감소했다. 당시 키워드 검색은 제공기관 일일 호출 제한 응답이어서
캐시되지 않았다.

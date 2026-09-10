# Cloud Run 일정 생성 메모리 안전 설정

일정 생성은 TourAPI 상세 조회와 Kakao 경로 계산을 병렬 수행하므로 일반 조회보다
메모리를 많이 사용한다. 애플리케이션은 인스턴스당 동시 생성 2개, 제한된 메모리
캐시, 고정 수의 경로 Worker를 사용한다.

Cloud Run 서비스에는 다음 값을 권장한다.

```text
Memory: 2 GiB
CPU: 2
Maximum requests per container: 2
```

Google Cloud Console에서 Cloud Run 서비스의 새 리비전을 편집하여 컨테이너의
메모리와 CPU를 변경하고, 컨테이너 확장 설정에서 최대 동시 요청 수를 2로 설정한다.
저장소에는 Cloud Run 서비스 선언 파일이 없으므로 이 인프라 값은 콘솔 또는 기존
배포 파이프라인에서 적용해야 한다.

Cloud Logging에서 `일정 생성 메모리 진단`을 검색하면 다음 단계를 확인할 수 있다.

```text
STARTED
RECOMMENDATIONS_RESOLVED
MATRIX_COMPLETED
SUPPLEMENT_MATRIX_COMPLETED
PLAN_SAVED
```

로그에는 현재 RSS, 후보 수, Matrix 노드 수가 포함된다. 인증 토큰과 API 키는
기록하지 않는다.

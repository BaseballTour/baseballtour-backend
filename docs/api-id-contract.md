# API ID 규칙

## 빈 목록 응답

목록 조회는 결과가 없어도 리소스가 존재하지 않는 오류가 아니다.

```json
{
  "success": true,
  "data": [],
  "meta": {
    "count": 0,
    "nextPageToken": null
  }
}
```

따라서 여행 목록, 경기 목록, 찜 컬렉션 목록, 검색 결과 및 여행 후보 목록은 빈 결과에 `200 OK`를 반환한다. 특정 ID로 상세·수정·삭제를 요청했는데 대상이 없을 때만 `404 NOT_FOUND`를 반환한다.

## ID 접두사

| 대상 | 형식 | 생성 주체 |
| --- | --- | --- |
| TourAPI 장소 | `tour_{contentId}` | TourAPI 변환 Adapter |
| 여행 | `trip_{hash}` | 여행 Repository |
| 찜 컬렉션 | `collection_{uuid}` | 찜 Repository |
| 일정 Plan | `plan_{uuid}` | 일정 Repository |
| 일정 Item | `item_{uuid}` | 일정 서비스 |
| 직관 로그 | `log_{uuid}` | 직관 로그 Repository |
| 로그 Entry | `entry_{uuid}` | 로그 Entry Repository |
| 경기 | `game_{providerKey}` | 경기 수집·Seed |

Firebase UID, KBO 구단 코드와 `gocheok`, `sajik` 같은 구장 slug는 외부 또는 업무 기준키이므로 별도의 접두사를 강제하지 않는다.

기존 Firestore 자동 ID 문서는 계속 조회할 수 있다. 이번 규칙은 새로 생성되는 문서부터 적용하며, 개발용 기존 데이터는 삭제 후 다시 만드는 것을 권장한다.

## Idempotency-Key

`Idempotency-Key`는 응답 데이터를 확인하기 위한 키가 아니라 생성 요청의 네트워크 재시도로 같은 문서가 두 번 생기는 것을 막는 요청 식별자다.

- 최초 요청: 문서를 생성하고 `201`을 반환한다.
- 같은 사용자·같은 키·같은 요청: 기존 여행을 반환한다.
- 같은 사용자·같은 키·다른 요청: `409 IDEMPOTENCY_CONFLICT`를 반환한다.

프론트는 사용자가 여행 생성 버튼을 누를 때 UUID를 한 번 만들고, 응답을 받지 못해 같은 요청을 재시도할 때 그 값을 유지한다. 사용자가 새 여행을 명시적으로 다시 생성할 때는 새 키를 만든다.

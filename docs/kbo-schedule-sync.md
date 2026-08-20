# KBO 경기 일정 동기화

## 목적과 범위

KBO 홈페이지의 월별 경기 일정 데이터를 배치에서 수집해 기존 Firestore
`games` 컬렉션으로 정규화한다. 앱의 `GET /api/v1/games` 요청 중에는 KBO
사이트를 호출하지 않는다.

KBO 홈페이지 내부 요청은 공개 OpenAPI 계약이 아니다. 사전 고지 없이
응답이 바뀔 수 있으므로 상업적 이용·장기 운영 전에는 KBO에 이용 허가와
허용 범위를 확인해야 한다. 수집기는 월 단위 한 번 호출하고, 응답 구조가
달라지면 잘못된 데이터를 저장하지 않고 실패하도록 구성했다.

## 데이터 흐름

```text
KBO 월별 일정 내부 요청
  -> KboScheduleClient
  -> parse_schedule_response (팀·구장·상태 정규화)
  -> KboScheduleSyncService
  -> Firestore games
  -> 기존 GET /api/v1/games
```

문서 ID는 `kbo_날짜_원정팀_홈팀_구장_순번`으로 결정한다. 같은 경기를
다시 동기화하면 기존 문서를 갱신하며 `createdAt`은 유지한다. 점수는 KBO
표의 원정팀-홈팀 순서를 내부 `awayScore`와 `homeScore`로 변환한다.

현재 Seed에 없는 임시·제2구장(예: 울산, 포항, 청주)은 잘못 연결하지 않고
건너뛴 이유를 출력한다. 해당 구장을 운영 범위에 넣을 때 stadium Seed와
매핑을 함께 추가한다.

## 로컬 실행

기본 실행은 Firestore에 쓰지 않는 dry-run이다.

```bash
uv run python -m scripts.sync_kbo_games --year 2026 --month 8
```

출력과 건너뜀 사유를 검토한 후에만 실제 저장을 실행한다.

```bash
uv run python -m scripts.sync_kbo_games --year 2026 --month 8 --write
```

`--write`에는 Firebase 서비스 계정 설정과 구단·구장 Seed가 필요하다.

## 권장 배치 주기

- 시즌 전체 일정: 하루 1회(월별 호출 사이에 간격 적용)
- 당일 취소·변경 확인: 경기일 10~30분 간격
- 경기 종료 시간대 결과 확인: 10분 간격

Cloud Run Job에서는 필요한 월만 실행한다. 여러 월을 동기화할 경우 각 월
요청 사이에 충분한 간격을 두고, 동시 호출하지 않는다.

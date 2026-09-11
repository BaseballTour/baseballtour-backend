# 선수 추천 맛집 Firestore 입력 결과

입력일: 2026-09-02

컬렉션: `playerPlaceRecommendations`

## 저장 결과

- 원본에서 읽은 선수·장소 조합: 186건
- Firestore 저장 완료: 184건
- 주소 또는 현재 장소를 확인하지 못해 제외: 2건
- 동일 구장·선수·장소 조합은 결정적 문서 ID로 upsert하여 재실행 시
  중복 생성하지 않는다.

### 구장별 저장 건수

| stadiumId | 건수 |
| --- | ---: |
| `changwon` | 22 |
| `incheon` | 22 |
| `gwangju` | 20 |
| `jamsil` | 54 |
| `sajik` | 17 |
| `daegu` | 16 |
| `gocheok` | 2 |
| `daejeon` | 23 |
| `suwon` | 8 |

`jamsil`은 LG 48건과 두산 6건을 합한 수치다.

### Kakao 연결 결과

| 연결 방식 | 건수 | 의미 |
| --- | ---: | --- |
| Kakao 장소 ID 확정 | 125 | 장소명·주소로 동일 장소를 하나로 확정 |
| 주소 기반 보완 필요 | 59 | Kakao 장소 ID를 추가로 검수해야 하는 항목 |

위 수치는 2026-09-02 당시 입력 결과다. 현재 저장 정책은 장소명·주소와
`kakaoPlaceId`만 영구 저장하고 Kakao 응답 본문은 저장하지 않는다.

## 저장하지 않은 항목

| 구단/구장 | 선수 | 장소 | 사유 |
| --- | --- | --- | --- |
| SSG/`incheon` | 최정 | 송도복집 | 현재 장소와 주소 모두 확인 불가 |
| SSG/`incheon` | 김광현 | 원조태양생고기 | 현재 장소와 주소 모두 확인 불가 |

이 항목은 최신 도로명 주소나 Kakao 장소 링크를 확보한 뒤 다시 입력한다.

## 현재 운영 방식

선수 추천 장소는 TourAPI에서 조회하지 않는다. Firestore의 큐레이션
장소명·주소와 `kakaoPlaceId`를 기준으로 Kakao Local을 실시간 조회해
좌표·전화번호·지도 링크를 공통 `Place` 응답에 일시 결합한다.

초기 입력과 관리자 갱신은 다음 반자동 절차를 사용한다.

1. Markdown 원본을 Kakao 장소 검색 또는 주소 좌표 변환으로 한 번 확인한다.
2. 검수 JSON에는 큐레이션 값과 확정된 `kakaoPlaceId`만 남긴다.
3. `seed_player_picks --write`로 최소 스키마를 upsert한다.
4. 영업시간은 저장하지 않고 `MISSING`으로 처리한다.

```powershell
uv run python -m scripts.import_player_pick_markdown `
  --input "jamsil=C:\path\LG.md" `
  --review-output "player-picks-review.json"

uv run python -m scripts.seed_player_picks `
  --input "player-picks-review.json" `
  --write
```

입력 시 Kakao는 동일 장소의 ID를 확정하는 데만 사용한다. 운영 조회에서는
좌표·전화번호·지도 링크를 최신 응답에서 사용하지만 Firestore로 다시
저장하지 않는다. Kakao Local에 없는 영업시간은 `MISSING`으로 반환하고
화면에서 `운영시간 확인 필요`와 지도 링크를 표시한다.

## 수동 보완 항목

- 정보근 추천 `화로우`: `부산광역시 강서구 명지국제6로232번길 8 1층`,
  추천 설명 `선수 부모님이 운영하는 가게`를 함께 저장했다.
- 전의산·고명준 추천 `김가네 감자탕`: 두 선수 추천 문서에
  `인천 강화군 길상면 마니산로 56`을 적용했다.

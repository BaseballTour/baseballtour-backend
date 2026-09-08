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

### 장소 원천별 저장 건수

| Place.source | 건수 | 의미 |
| --- | ---: | --- |
| `KAKAO` | 125 | Kakao 장소명·주소 또는 현재 동일 시군구 장소 확인 |
| `LOCAL_DATA` | 59 | 관리자 원본 주소를 Kakao 주소 검색으로 좌표 검증 |

Kakao와 `LOCAL_DATA`는 수작업으로 확정한 선수 추천 위치를 표현하기
위한 것이며 일반 장소 자동 추천 후보 풀에는 넣지 않는다.

## 저장하지 않은 항목

| 구단/구장 | 선수 | 장소 | 사유 |
| --- | --- | --- | --- |
| SSG/`incheon` | 최정 | 송도복집 | 현재 장소와 주소 모두 확인 불가 |
| SSG/`incheon` | 김광현 | 원조태양생고기 | 현재 장소와 주소 모두 확인 불가 |

이 항목은 최신 도로명 주소나 Kakao 장소 링크를 확보한 뒤 다시 입력한다.

## 현재 운영 방식

선수 추천 장소는 요청 시 TourAPI에서 상세정보를 다시 조회하지 않는다.
`playerPlaceRecommendations.placeSnapshot`을 유일한 운영 조회 원천으로
사용하여 외부 API 장애와 장소 정보 변경이 일정 생성에 직접 영향을 주지
않게 한다.

초기 입력과 관리자 갱신은 다음 반자동 절차를 사용한다.

1. Markdown 원본을 Kakao 장소 검색 또는 주소 좌표 변환으로 한 번 확인한다.
2. `--review-output`으로 장소 기본정보와 누락 필드가 표시된 JSON을 만든다.
3. 영업시간·휴무일처럼 일정 계산에 필요한 값만 공식 출처로 확인해 JSON의
   `placeSnapshot`을 보완한다.
4. 보완한 JSON을 `seed_player_picks --write`로 upsert한다.

```powershell
uv run python -m scripts.import_player_pick_markdown `
  --input "jamsil=C:\path\LG.md" `
  --review-output "player-picks-review.json"

uv run python -m scripts.seed_player_picks `
  --input "player-picks-review.json" `
  --write
```

검수 JSON에 `placeSnapshot`이 들어간 뒤에는 두 번째 명령이 TourAPI나
Kakao를 호출하지 않는다. `review.missingFields`는 대표 이미지, 전화번호,
요일별 영업시간, 휴무일 중 확인할 항목을 알려준다. 확인되지 않은 영업정보는
추측해 입력하지 않고 `MISSING` 상태로 두며 화면에서 카카오맵 링크를 통해
최신 정보를 확인하게 한다.

## 수동 보완 항목

- 정보근 추천 `화로우`: `부산광역시 강서구 명지국제6로232번길 8 1층`,
  추천 설명 `선수 부모님이 운영하는 가게`를 함께 저장했다.
- 전의산·고명준 추천 `김가네 감자탕`: 두 선수 추천 문서에
  `인천 강화군 길상면 마니산로 56`을 적용했다.

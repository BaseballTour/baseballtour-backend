# 선수 추천 장소 저장 정책

## Firestore 영구 저장 필드

- `stadiumId`, `playerName`, `playerPosition`
- `placeName`, `address`, `category`
- `kakaoPlaceId`
- `recommendationNote`, `createdAt`, `updatedAt`

`placeName`, `address`, `category`, 추천 설명은 팀이 독립적으로 확인하고
관리하는 큐레이션 데이터다. `kakaoPlaceId`는 최신 장소 정보를 조회하기
위한 연결 키다.

## 저장하지 않는 필드

- 전체 `placeSnapshot`
- Kakao에서 받은 좌표, 전화번호, 지도 URL
- TourAPI 전용 ID와 신분류 코드
- `distanceMeters`
- 영업시간, 휴무일, 입장 마감 관련 필드
- 대표 이미지와 소개문

좌표·전화번호·지도 링크는 응답을 만들 때 Kakao Local에서 조회해 공통
`Place` 형식으로 일시 결합한다. Kakao 조회에 실패한 추천 장소는 해당
응답에서 제외하고 경고 로그를 남긴다.

Kakao Local은 영업시간을 제공하지 않으므로 선수 추천 장소의 영업시간은
`MISSING`이다. 확인되지 않은 시간을 알고리즘 제약에 사용하지 않으며,
화면에는 `운영시간 확인 필요`와 최신 지도 링크를 표시한다.

## 기존 문서 정리

먼저 dry-run으로 확인하고 실제 교체를 실행한다.

```powershell
python -m scripts.migrate_player_pick_documents
python -m scripts.migrate_player_pick_documents --write
python -m scripts.validate_player_pick_snapshots
```

마이그레이션은 문서를 `merge`하지 않고 통째로 교체하므로 기존
`placeSnapshot`, `placeId`, `curationKey`와 그 안의 불필요한 필드가
남지 않는다.

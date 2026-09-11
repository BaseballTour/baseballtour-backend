"""Firestore 선수 추천 문서의 최소 필드와 Kakao 연결 현황을 검사합니다."""

from app.repositories.player_pick_repository import PlayerPickRepository


def main() -> None:
    repository = PlayerPickRepository()
    invalid_ids: list[str] = []
    missing_link_ids: list[str] = []
    total = 0
    for snapshot in repository._collection.stream():
        total += 1
        data = snapshot.to_dict() or {}
        if not all(data.get(field) for field in ("stadiumId", "playerName", "placeName", "address")):
            invalid_ids.append(snapshot.id)
        if not data.get("kakaoPlaceId"):
            missing_link_ids.append(snapshot.id)
    if invalid_ids:
        raise SystemExit("필수 큐레이션 필드 누락: " + ", ".join(invalid_ids))
    print(f"검증 완료: 전체 {total}, Kakao ID 연결 {total - len(missing_link_ids)}")
    print(
        f"주소 좌표 변환 fallback 사용 {len(missing_link_ids)}"
        " (오류가 아니며 장소명·주소로 조회됩니다.)"
    )


if __name__ == "__main__":
    main()

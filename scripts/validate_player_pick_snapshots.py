"""Firestore 선수 추천 문서의 Kakao 연결 ID 누락 여부를 검사합니다."""

from app.repositories.player_pick_repository import PlayerPickRepository


def main() -> None:
    missing_ids = PlayerPickRepository().get_missing_kakao_link_ids()
    if missing_ids:
        raise SystemExit("Kakao 연결 ID 누락: " + ", ".join(missing_ids))
    print("모든 선수 추천 문서에 kakaoPlaceId가 있습니다.")


if __name__ == "__main__":
    main()

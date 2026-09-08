"""Firestore 선수 추천 문서의 placeSnapshot 완전성을 검사합니다."""

from app.repositories.player_pick_repository import PlayerPickRepository


def main() -> None:
    missing_ids = PlayerPickRepository().get_missing_snapshot_ids()
    if missing_ids:
        print(f"snapshot 누락: {len(missing_ids)}건")
        for player_pick_id in missing_ids:
            print(f"- {player_pick_id}")
        raise SystemExit(1)
    print("선수 추천 장소 snapshot 검사 완료: 누락 0건")


if __name__ == "__main__":
    main()

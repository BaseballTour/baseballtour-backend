import argparse
from datetime import datetime, timezone

from app.core.firebase import get_firestore_client
from app.repositories.favorite_collection_repository import (
    FavoriteCollectionRepository,
)
from app.repositories.place_favorite_stats_repository import (
    PlaceFavoriteStatsRepository,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="기존 찜 데이터로 장소별 고유 사용자 수를 보충합니다.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="지정할 때만 통계 문서를 갱신합니다. 기본값은 dry-run입니다.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client = get_firestore_client()
    favorites = FavoriteCollectionRepository(client)
    stats = PlaceFavoriteStatsRepository(client)
    pairs: list[tuple[str, str]] = []

    for user_snapshot in client.collection("users").stream():
        for place_id in favorites.get_unique_place_ids(
            user_id=user_snapshot.id,
        ):
            pairs.append((user_snapshot.id, place_id))

    if args.write:
        now = datetime.now(timezone.utc)
        for user_id, place_id in pairs:
            stats.add_user(
                place_id=place_id,
                user_id=user_id,
                updated_at=now,
            )

    mode = "WRITE" if args.write else "DRY-RUN"
    print(f"[{mode}] 고유 사용자-장소 찜 관계 {len(pairs)}건")


if __name__ == "__main__":
    main()

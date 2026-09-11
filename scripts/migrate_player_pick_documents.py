"""선수 추천 문서를 최소 보관 스키마로 교체합니다. 기본은 dry-run입니다."""

import argparse
from datetime import datetime, timezone

from app.repositories.player_pick_repository import PlayerPickRepository
from app.schemas.player_pick import PlayerPickDocument


REMOVED_TOP_LEVEL_FIELDS = {"curationKey", "placeId", "placeSnapshot"}


def _clean_document(data: dict) -> PlayerPickDocument:
    legacy = data.get("placeSnapshot") or {}
    place_id = str(data.get("placeId") or "")
    kakao_place_id = (
        data.get("kakaoPlaceId")
        or legacy.get("kakaoPlaceId")
        or (place_id.removeprefix("kakao_") if place_id.startswith("kakao_") else None)
    )
    return PlayerPickDocument(
        stadium_id=data.get("stadiumId"),
        player_name=data.get("playerName"),
        player_position=data.get("playerPosition"),
        place_name=data.get("placeName") or legacy.get("name"),
        address=data.get("address") or legacy.get("address") or "",
        category=data.get("category") or legacy.get("category") or "RESTAURANT",
        kakao_place_id=kakao_place_id,
        recommendation_note=data.get("recommendationNote"),
        created_at=data.get("createdAt") or datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


def migrate(*, write: bool) -> tuple[int, int]:
    repository = PlayerPickRepository()
    updated = skipped = 0
    for snapshot in repository._collection.stream():
        data = snapshot.to_dict() or {}
        try:
            document = _clean_document(data)
        except Exception as exc:
            print(f"[건너뜀] {snapshot.id}: {type(exc).__name__}: {exc}")
            skipped += 1
            continue
        removed = sorted(set(data) & REMOVED_TOP_LEVEL_FIELDS)
        print(
            f"[{'교체' if write else 'DRY-RUN'}] {snapshot.id} / "
            f"{document.place_name} / 제거={','.join(removed) or '없음'}"
        )
        if write:
            # merge하지 않아 placeSnapshot과 그 안의 Kakao 복제값을 완전히 제거한다.
            snapshot.reference.set(
                document.model_dump(by_alias=True, exclude_none=False)
            )
        updated += 1
    return updated, skipped


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    updated, skipped = migrate(write=args.write)
    print(f"완료: 대상 {updated}, 건너뜀 {skipped}")


if __name__ == "__main__":
    main()

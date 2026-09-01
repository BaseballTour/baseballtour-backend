import argparse
import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.external.tour_api.adapter import tour_api_adapter
from app.models.place import Place
from app.repositories.player_pick_repository import PlayerPickRepository
from app.schemas.player_pick import PlayerPickDocument


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "장소명·주소로 TourAPI 장소를 확인하고 선수추천 DB에 저장합니다. "
            "기본값은 dry-run입니다."
        )
    )
    parser.add_argument("--input", required=True, help="선수추천 JSON 경로")
    parser.add_argument(
        "--write",
        action="store_true",
        help="검증된 항목을 Firestore에 저장합니다.",
    )
    return parser.parse_args()


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", value.casefold())


def _score_candidate(
    candidate: Place,
    *,
    place_name: str,
    address: str,
) -> int:
    expected_name = _normalize(place_name)
    actual_name = _normalize(candidate.name)
    expected_address = _normalize(address)
    actual_address = _normalize(candidate.address or "")
    score = 0
    if expected_name == actual_name:
        score += 100
    elif expected_name in actual_name or actual_name in expected_name:
        score += 50
    if expected_address and (
        expected_address in actual_address or actual_address in expected_address
    ):
        score += 40
    return score


async def _resolve_place(row: dict[str, Any]) -> Place | None:
    place_id = str(row.get("placeId") or "").strip()
    if place_id.startswith("tour_"):
        return await tour_api_adapter.get_place_detail(
            place_id.removeprefix("tour_")
        )

    place_name = str(row.get("placeName") or "").strip()
    address = str(row.get("address") or "").strip()
    if not place_name or not address:
        raise ValueError("placeId가 없으면 placeName과 address가 필요합니다.")
    page = await tour_api_adapter.search_place_page(
        keyword=place_name,
        page_no=1,
        num_of_rows=20,
    )
    ranked = sorted(
        (
            (_score_candidate(place, place_name=place_name, address=address), place)
            for place in page.places
        ),
        key=lambda item: (-item[0], item[1].place_id),
    )
    if not ranked or ranked[0][0] < 50:
        return None
    if len(ranked) > 1 and ranked[0][0] == ranked[1][0]:
        print(
            f"[확인 필요] {place_name}: 동점 후보 "
            + ", ".join(place.name for _, place in ranked[:5])
        )
        return None
    selected = ranked[0][1]
    try:
        return await tour_api_adapter.get_place_detail(
            selected.place_id.removeprefix("tour_")
        )
    except Exception:
        return selected


async def main() -> None:
    args = parse_args()
    input_path = Path(args.input).resolve()
    rows = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("입력 JSON의 최상위 값은 배열이어야 합니다.")
    repository = PlayerPickRepository() if args.write else None
    resolved_count = 0
    skipped_count = 0
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            print(f"[건너뜀] #{index}: 객체 형식이 아닙니다.")
            skipped_count += 1
            continue
        try:
            place = await _resolve_place(row)
        except Exception as exc:
            print(f"[건너뜀] #{index}: {type(exc).__name__}: {exc}")
            skipped_count += 1
            continue
        if place is None:
            print(f"[건너뜀] #{index}: 일치하는 TourAPI 장소를 확정하지 못했습니다.")
            skipped_count += 1
            continue
        try:
            now = datetime.now(timezone.utc)
            document = PlayerPickDocument(
                stadium_id=str(row.get("stadiumId") or "").strip(),
                player_name=str(row.get("playerName") or "").strip(),
                place_id=place.place_id,
                place_snapshot=place,
                created_at=now,
                updated_at=now,
            )
            if repository is None:
                print(
                    f"[DRY-RUN] {document.stadium_id} / "
                    f"{document.player_name} / {place.name} / "
                    f"{place.address} / {place.place_id}"
                )
            else:
                record = repository.upsert(document)
                print(
                    f"[저장] {record.player_pick_id} / "
                    f"{record.player_name} / "
                    f"{record.place_snapshot.name if record.place_snapshot else record.place_id}"
                )
        except Exception as exc:
            print(f"[건너뜀] #{index}: {type(exc).__name__}: {exc}")
            skipped_count += 1
            continue
        resolved_count += 1
    print(
        f"완료: 입력 {len(rows)}, 확정 {resolved_count}, 건너뜀 {skipped_count}, "
        f"모드 {'WRITE' if args.write else 'DRY-RUN'}"
    )


if __name__ == "__main__":
    asyncio.run(main())

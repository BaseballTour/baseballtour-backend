import argparse
import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.external.kakao.client import search_place_page
from app.external.kakao.mapper import kakao_address
from app.repositories.player_pick_repository import PlayerPickRepository
from app.schemas.player_pick import PlayerPickDocument


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Kakao 장소 ID만 확인해 선수추천 DB에 저장합니다. 기본은 dry-run입니다."
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def _normalize(value: str) -> str:
    normalized = value.casefold()
    aliases = {
        "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구",
        "대전광역시": "대전", "인천광역시": "인천", "광주광역시": "광주",
        "경기도": "경기", "경상남도": "경남",
    }
    for source, target in aliases.items():
        normalized = normalized.replace(source, target)
    return re.sub(r"[^0-9a-z가-힣]", "", normalized)


def _address_matches(expected: str, actual: str) -> bool:
    expected_value, actual_value = _normalize(expected), _normalize(actual)
    return bool(
        expected_value and actual_value
        and (expected_value in actual_value or actual_value in expected_value)
    )


def _same_region(expected: str, actual: str) -> bool:
    def parts(value: str) -> tuple[str | None, str | None]:
        normalized = _normalize(value)
        region = next(
            (name for name in ("서울", "인천", "경기", "대전", "광주", "대구", "부산", "경남") if name in normalized),
            None,
        )
        district = re.search(r"([가-힣]+(?:구|군))", value)
        return region, district.group(1) if district else None

    expected_parts, actual_parts = parts(expected), parts(actual)
    return expected_parts[0] is not None and expected_parts == actual_parts


async def _resolve_kakao_id(*, place_name: str, address: str) -> str | None:
    page = await search_place_page(place_name, size=15)
    candidates: set[str] = set()
    for item in page.documents:
        kakao_id = str(item.get("id") or "").strip()
        candidate_name = str(item.get("place_name") or "").strip()
        expected_name, actual_name = _normalize(place_name), _normalize(candidate_name)
        similar_name = expected_name in actual_name or actual_name in expected_name
        candidate_address = kakao_address(item)
        if kakao_id and similar_name and (
            _address_matches(address, candidate_address)
            or (expected_name == actual_name and _same_region(address, candidate_address))
        ):
            candidates.add(kakao_id)
    return next(iter(candidates)) if len(candidates) == 1 else None


def _review_row(document: PlayerPickDocument, player_pick_id: str) -> dict[str, Any]:
    return {
        "playerPickId": player_pick_id,
        **document.model_dump(mode="json", by_alias=True),
    }


async def seed_rows(rows: list[Any], *, write: bool = False) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise ValueError("입력 JSON의 최상위 값은 배열이어야 합니다.")
    repository = PlayerPickRepository() if write else None
    review_rows: list[dict[str, Any]] = []
    skipped = 0
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            skipped += 1
            continue
        place_name = str(row.get("placeName") or "").strip()
        address = str(row.get("address") or "").strip()
        if not place_name or not address:
            print(f"[건너뜀] #{index}: placeName과 address가 필요합니다.")
            skipped += 1
            continue
        try:
            kakao_place_id = (
                str(row.get("kakaoPlaceId") or "").strip()
                or await _resolve_kakao_id(place_name=place_name, address=address)
            )
            if not kakao_place_id:
                print(f"[건너뜀] #{index}: Kakao 장소를 하나로 확정하지 못했습니다.")
                skipped += 1
                continue
            now = datetime.now(timezone.utc)
            document = PlayerPickDocument(
                stadium_id=str(row.get("stadiumId") or "").strip(),
                player_name=str(row.get("playerName") or "").strip(),
                player_position=row.get("playerPosition") or None,
                place_name=place_name,
                address=address,
                category=row.get("category") or "RESTAURANT",
                kakao_place_id=kakao_place_id,
                recommendation_note=str(row.get("recommendationNote") or "").strip() or None,
                created_at=now,
                updated_at=now,
            )
            player_pick_id = PlayerPickRepository.build_id(document)
            review_rows.append(_review_row(document, player_pick_id))
            if repository is None:
                print(f"[DRY-RUN] {document.stadium_id} / {document.player_name} / {place_name} / {address} / {kakao_place_id}")
            else:
                repository.upsert(player_pick_id, document)
                print(f"[저장] {player_pick_id} / {place_name}")
        except Exception as exc:
            print(f"[건너뜀] #{index}: {type(exc).__name__}: {exc}")
            skipped += 1
    print(f"완료: 입력 {len(rows)}, 확정 {len(review_rows)}, 건너뜀 {skipped}, 모드 {'WRITE' if write else 'DRY-RUN'}")
    return review_rows


async def main() -> None:
    args = parse_args()
    rows = json.loads(Path(args.input).resolve().read_text(encoding="utf-8"))
    await seed_rows(rows, write=args.write)


if __name__ == "__main__":
    asyncio.run(main())

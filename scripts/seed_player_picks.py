import argparse
import asyncio
import json
import re
from hashlib import sha256
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.external.kakao.client import (
    geocode_address,
    search_place_page as search_kakao_places,
)
from app.external.kakao.mapper import (
    kakao_address,
    kakao_category_to_place_category,
)
from app.models.place import (
    Place,
    PlaceSource,
    default_stay_minutes_for,
)
from app.repositories.player_pick_repository import PlayerPickRepository
from app.schemas.player_pick import PlayerPickDocument


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "장소명·주소로 Kakao 장소를 확인하고 선수추천 DB에 저장합니다. "
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
    normalized = value.casefold()
    aliases = {
        "전남광주통합특별시": "광주",
        "전남광주": "광주",
        "광주광역시": "광주",
        "서울특별시": "서울",
        "부산광역시": "부산",
        "대구광역시": "대구",
        "대전광역시": "대전",
        "인천광역시": "인천",
        "경기도": "경기",
        "경상남도": "경남",
    }
    for source, target in aliases.items():
        normalized = normalized.replace(source, target)
    return re.sub(r"[^0-9a-z가-힣]", "", normalized)


def _address_matches(expected: str, actual: str) -> bool:
    expected_address = _normalize(expected)
    actual_address = _normalize(actual)
    if not expected_address or not actual_address:
        return False
    return (
        expected_address in actual_address
        or actual_address in expected_address
    )


def _same_region(expected: str, actual: str) -> bool:
    aliases = {
        "경상남도": "경남",
        "전남광주통합특별시": "광주",
        "전남광주": "광주",
        "광주광역시": "광주",
        "서울특별시": "서울",
        "부산광역시": "부산",
        "대구광역시": "대구",
        "대전광역시": "대전",
        "인천광역시": "인천",
        "경기도": "경기",
    }

    def parts(value: str) -> tuple[str | None, str | None]:
        for source, target in aliases.items():
            value = value.replace(source, target)
        region = next(
            (
                candidate
                for candidate in (
                    "서울", "인천", "경기", "대전", "광주",
                    "대구", "부산", "경남",
                )
                if candidate in value
            ),
            None,
        )
        district_match = re.search(r"([가-힣]+(?:구|군))", value)
        return region, district_match.group(1) if district_match else None

    expected_region, expected_district = parts(expected)
    actual_region, actual_district = parts(actual)
    return (
        expected_region is not None
        and expected_region == actual_region
        and expected_district is not None
        and expected_district == actual_district
    )


def _kakao_place(item: dict[str, Any]) -> Place | None:
    kakao_id = str(item.get("id") or "").strip()
    name = str(item.get("place_name") or "").strip()
    address = kakao_address(item)
    try:
        latitude = round(float(item.get("y")), 6)
        longitude = round(float(item.get("x")), 6)
    except (TypeError, ValueError):
        return None
    if not kakao_id or not name or not address:
        return None
    category = kakao_category_to_place_category(item.get("category_group_code"))
    return Place(
        place_id=f"kakao_{kakao_id}",
        name=name,
        category=category,
        latitude=latitude,
        longitude=longitude,
        address=address,
        telephone=str(item.get("phone") or "").strip() or None,
        default_stay_minutes=default_stay_minutes_for(category),
        source=PlaceSource.KAKAO,
        source_content_id=kakao_id,
        kakao_place_id=kakao_id,
        place_url=str(item.get("place_url") or "").strip() or None,
    )


async def _resolve_kakao_place(
    *,
    place_name: str,
    address: str,
) -> Place | None:
    # Kakao는 상세 주소를 검색어에 모두 넣으면 결과가 비는 경우가 많다.
    # 이름으로 후보를 넓게 찾은 뒤 주소를 로컬에서 엄격하게 대조한다.
    page = await search_kakao_places(place_name, size=15)
    candidates: list[Place] = []
    for item in page.documents:
        candidate = _kakao_place(item)
        if candidate is None:
            continue
        expected_name = _normalize(place_name)
        actual_name = _normalize(candidate.name)
        exact_name = actual_name == expected_name
        similar_name = (
            bool(expected_name and actual_name)
            and (
                expected_name in actual_name
                or actual_name in expected_name
            )
        )
        if (
            (similar_name and _address_matches(address, candidate.address))
            or (exact_name and _same_region(address, candidate.address))
        ):
            candidates.append(candidate)
    if len(candidates) != 1:
        if len(candidates) > 1:
            print(
                f"[확인 필요] {place_name}: Kakao 주소 일치 후보 "
                + ", ".join(place.name for place in candidates[:5])
            )
        return None
    return candidates[0]


def _geocoding_queries(address: str) -> list[str]:
    without_detail = re.sub(
        r"(?:,?\s*(?:지하\s*)?\d+(?:[·~\-]\d+)?층.*"
        r"|,?\s*\d+호.*)$",
        "",
        address,
    ).strip()
    before_comma = address.split(",", maxsplit=1)[0].strip()
    return list(dict.fromkeys((address.strip(), without_detail, before_comma)))


async def _resolve_manual_place(
    *,
    place_name: str,
    address: str,
) -> Place | None:
    for query in _geocoding_queries(address):
        documents = await geocode_address(query)
        if not documents:
            continue
        item = documents[0]
        try:
            latitude = round(float(item.get("y")), 6)
            longitude = round(float(item.get("x")), 6)
        except (TypeError, ValueError):
            continue
        identity = f"{_normalize(place_name)}:{_normalize(address)}"
        digest = sha256(identity.encode("utf-8")).hexdigest()[:24]
        return Place(
            place_id=f"player_place_{digest}",
            name=place_name,
            category="RESTAURANT",
            latitude=latitude,
            longitude=longitude,
            address=address,
            default_stay_minutes=60,
            source=PlaceSource.LOCAL_DATA,
            enriched_by=[PlaceSource.KAKAO],
        )
    return None


async def _resolve_place(row: dict[str, Any]) -> Place | None:
    snapshot = row.get("placeSnapshot")
    if isinstance(snapshot, dict):
        return Place.model_validate(snapshot)

    place_name = str(row.get("placeName") or "").strip()
    address = str(row.get("address") or "").strip()
    if not place_name or not address:
        raise ValueError("placeName과 address가 필요합니다.")
    kakao_place = await _resolve_kakao_place(
        place_name=place_name,
        address=address,
    )
    return kakao_place or await _resolve_manual_place(
        place_name=place_name,
        address=address,
    )


def _prepare_snapshot(
    place: Place,
    *,
    player_name: str,
    recommendation_note: str | None,
) -> Place:
    overview = place.overview or (
        f"{player_name} 선수가 추천한 {place.name}입니다."
    )
    return place.model_copy(
        update={
            "overview": overview,
            "recommendation_note": recommendation_note,
        }
    )


def _review_row(document: PlayerPickDocument) -> dict[str, Any]:
    place = document.place_snapshot
    assert place is not None
    missing_fields = [
        name
        for name, value in (
            ("thumbnailUrl", place.thumbnail_url),
            ("telephone", place.telephone),
            ("businessHoursRules", place.business_hours_rules),
            ("closedDaysText", place.closed_days_text),
        )
        if not value
    ]
    return {
        "stadiumId": document.stadium_id,
        "playerName": document.player_name,
        "placeName": place.name,
        "address": place.address,
        "recommendationNote": document.recommendation_note,
        "placeSnapshot": place.model_dump(mode="json", by_alias=True),
        "review": {
            "status": "NEEDS_REVIEW" if missing_fields else "COMPLETE",
            "missingFields": missing_fields,
            "instructions": (
                "공식 출처로 확인한 값만 placeSnapshot에 입력한 뒤 "
                "이 JSON을 --input으로 다시 실행하세요."
            ),
        },
    }


async def seed_rows(
    rows: list[Any], *, write: bool = False
) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise ValueError("입력 JSON의 최상위 값은 배열이어야 합니다.")
    repository = PlayerPickRepository() if write else None
    resolved_count = 0
    skipped_count = 0
    review_rows: list[dict[str, Any]] = []
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
            print(f"[건너뜀] #{index}: 이름과 주소가 일치하는 장소를 확정하지 못했습니다.")
            skipped_count += 1
            continue
        try:
            now = datetime.now(timezone.utc)
            player_name = str(row.get("playerName") or "").strip()
            recommendation_note = (
                str(row.get("recommendationNote") or "").strip() or None
            )
            place = _prepare_snapshot(
                place,
                player_name=player_name,
                recommendation_note=recommendation_note,
            )
            document = PlayerPickDocument(
                stadium_id=str(row.get("stadiumId") or "").strip(),
                player_name=player_name,
                place_id=place.place_id,
                place_snapshot=place,
                recommendation_note=recommendation_note,
                curation_key=sha256(
                    (
                        f"{_normalize(str(row.get('placeName') or place.name))}:"
                        f"{_normalize(str(row.get('address') or place.address))}"
                    ).encode("utf-8")
                ).hexdigest()[:24],
                created_at=now,
                updated_at=now,
            )
            review_rows.append(_review_row(document))
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
        f"모드 {'WRITE' if write else 'DRY-RUN'}"
    )
    return review_rows


async def main() -> None:
    args = parse_args()
    input_path = Path(args.input).resolve()
    rows = json.loads(input_path.read_text(encoding="utf-8"))
    await seed_rows(rows, write=args.write)


if __name__ == "__main__":
    asyncio.run(main())

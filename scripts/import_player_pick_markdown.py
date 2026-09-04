import argparse
import asyncio
import re
from pathlib import Path

from scripts.seed_player_picks import seed_rows


PLAYER_HEADING = re.compile(r"^\*\*(.+?)\*\*(.*)$")
KIA_PLAYER = re.compile(r"^-\s+([^(*]+?)\s*$")
PLACE_WITH_ADDRESS = re.compile(r"^-?\s*(.+?)\s*\(([^()]+)\)(.*)$")
LG_COMMON_PICK = re.compile(
    r"^LG 전체 선수 맛집\s*-\s*(.+?)\s*\(([^()]+)\)"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="구단별 선수 추천 맛집 Markdown을 Firestore 입력으로 변환합니다."
    )
    parser.add_argument(
        "--input",
        action="append",
        required=True,
        metavar="STADIUM_ID=PATH",
        help="구장 ID와 Markdown 경로. 여러 번 지정할 수 있습니다.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="검증된 항목을 Firestore에 저장합니다. 기본값은 dry-run입니다.",
    )
    return parser.parse_args()


def _split_players(value: str) -> list[str]:
    cleaned = re.sub(r"\s*\([^)]*\)\s*$", "", value).strip()
    return [part.strip() for part in cleaned.split(",") if part.strip()]


def parse_markdown(path: Path, stadium_id: str) -> tuple[list[dict], list[str]]:
    rows: list[dict] = []
    skipped: list[str] = []
    players: list[str] = []
    heading_note: str | None = None
    last_row_indexes: list[int] = []
    is_kia_format = path.name.startswith("기아 ")

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("!["):
            continue

        common_match = LG_COMMON_PICK.match(line)
        if common_match:
            rows.append(
                {
                    "stadiumId": stadium_id,
                    "playerName": "LG 전체 선수",
                    "placeName": common_match.group(1).strip(),
                    "address": common_match.group(2).strip(),
                }
            )
            last_row_indexes = [len(rows) - 1]
            continue

        heading_match = PLAYER_HEADING.match(line)
        if heading_match:
            heading_value = heading_match.group(1)
            players = _split_players(heading_value)
            inner_notes = re.findall(r"\(([^)]*)\)", heading_value)
            outer_note = heading_match.group(2).strip(" —-()")
            heading_note = " · ".join(
                part.strip() for part in (*inner_notes, outer_note) if part.strip()
            ) or None
            last_row_indexes = []
            continue

        if is_kia_format:
            player_match = KIA_PLAYER.match(line)
            if player_match and "(" not in line:
                players = _split_players(player_match.group(1))
                heading_note = None
                last_row_indexes = []
                continue

        place_match = PLACE_WITH_ADDRESS.match(line)
        if place_match and players:
            place_name = place_match.group(1).strip().lstrip("- ").strip()
            address = place_match.group(2).strip()
            inline_note = place_match.group(3).strip(" —-⭐") or None
            note = " · ".join(
                part for part in (heading_note, inline_note) if part
            ) or None
            last_row_indexes = []
            for player in players:
                row = {
                    "stadiumId": stadium_id,
                    "playerName": player,
                    "placeName": place_name,
                    "address": address,
                }
                if note:
                    row["recommendationNote"] = note
                rows.append(row)
                last_row_indexes.append(len(rows) - 1)
            continue

        if last_row_indexes and line.startswith(("※", "특히")):
            extra_note = line.lstrip("※ ").strip()
            for row_index in last_row_indexes:
                previous = rows[row_index].get("recommendationNote")
                rows[row_index]["recommendationNote"] = (
                    f"{previous} · {extra_note}" if previous else extra_note
                )
            continue

        if line.startswith("-") and players:
            skipped.append(f"{','.join(players)}: {line.lstrip('- ').strip()}")

    return rows, skipped


def _parse_input(value: str) -> tuple[str, Path]:
    stadium_id, separator, raw_path = value.partition("=")
    if not separator or not stadium_id.strip() or not raw_path.strip():
        raise ValueError("--input은 STADIUM_ID=PATH 형식이어야 합니다.")
    path = Path(raw_path.strip()).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Markdown 파일을 찾을 수 없습니다: {path}")
    return stadium_id.strip(), path


async def main() -> None:
    args = parse_args()
    rows: list[dict] = []
    skipped: list[str] = []
    for value in args.input:
        stadium_id, path = _parse_input(value)
        parsed, unparsed = parse_markdown(path, stadium_id)
        rows.extend(parsed)
        skipped.extend(f"{path.name}: {item}" for item in unparsed)

    print(f"Markdown 변환: 저장 후보 {len(rows)}, 주소 없음/형식 확인 {len(skipped)}")
    for item in skipped:
        print(f"[문서 확인 필요] {item}")
    await seed_rows(rows, write=args.write)


if __name__ == "__main__":
    asyncio.run(main())

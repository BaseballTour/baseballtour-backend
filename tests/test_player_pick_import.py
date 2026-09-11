from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.schemas.player_pick import PlayerPickDocument
from scripts.import_player_pick_markdown import parse_markdown
from scripts.seed_player_picks import _address_matches, _review_row, _same_region


def test_parse_markdown_expands_shared_player_heading(tmp_path: Path) -> None:
    source = tmp_path / "team.md"
    source.write_text(
        "# 구단\n\n**선수A, 선수B**\n- 식당명 (서울 송파구 테스트로 1)\n",
        encoding="utf-8",
    )
    rows, skipped = parse_markdown(source, "jamsil")
    assert skipped == []
    assert [row["playerName"] for row in rows] == ["선수A", "선수B"]


def test_address_matching_rejects_other_region() -> None:
    assert _address_matches("부산 연제구 거제천로 207", "부산광역시 연제구 거제천로 207")
    assert not _address_matches("부산 연제구 거제천로 207", "서울 성북구 창경궁로 140")
    assert _same_region("인천 강화군 전등사로 66", "인천광역시 강화군 길상로 255")


def test_review_document_contains_no_kakao_snapshot_or_hours() -> None:
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    document = PlayerPickDocument(
        stadium_id="jamsil",
        player_name="테스트",
        place_name="선수 추천 식당",
        address="서울 송파구",
        kakao_place_id="123",
        created_at=now,
        updated_at=now,
    )
    review = _review_row(document, "player_pick_001")
    assert review["placeName"] == "선수 추천 식당"
    assert review["kakaoPlaceId"] == "123"
    assert "placeSnapshot" not in review
    assert "businessHoursRules" not in review

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.models.place import Place, PlaceSource
from app.schemas.player_pick import PlayerPickDocument
from scripts.import_player_pick_markdown import parse_markdown
from scripts.seed_player_picks import (
    _address_matches,
    _prepare_snapshot,
    _review_row,
    _same_region,
)


def test_parse_markdown_expands_shared_player_heading(tmp_path: Path) -> None:
    source = tmp_path / "team.md"
    source.write_text(
        "# 구단\n\n**선수A, 선수B**\n- 식당명 (서울 송파구 테스트로 1)\n",
        encoding="utf-8",
    )

    rows, skipped = parse_markdown(source, "jamsil")

    assert skipped == []
    assert rows == [
        {
            "stadiumId": "jamsil",
            "playerName": "선수A",
            "placeName": "식당명",
            "address": "서울 송파구 테스트로 1",
        },
        {
            "stadiumId": "jamsil",
            "playerName": "선수B",
            "placeName": "식당명",
            "address": "서울 송파구 테스트로 1",
        },
    ]


def test_parse_markdown_reports_place_without_address(tmp_path: Path) -> None:
    source = tmp_path / "team.md"
    source.write_text(
        "# 구단\n\n**선수A**\n- 주소 없는 식당\n",
        encoding="utf-8",
    )

    rows, skipped = parse_markdown(source, "jamsil")

    assert rows == []
    assert skipped == ["선수A: 주소 없는 식당"]


def test_address_matching_rejects_same_name_in_other_region() -> None:
    assert _address_matches(
        "부산 연제구 거제천로 207",
        "부산광역시 연제구 거제천로 207",
    )
    assert not _address_matches(
        "부산 연제구 거제천로 207",
        "서울 성북구 창경궁로35다길 140",
    )
    assert _same_region(
        "인천 강화군 전등사로 66-3",
        "인천광역시 강화군 길상로 255",
    )
    assert not _same_region(
        "인천 강화군 전등사로 66-3",
        "인천 부평구 대정로 50",
    )


def test_parse_markdown_keeps_heading_inline_and_followup_notes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "team.md"
    source.write_text(
        "**선수A (통역)** (선수단 공통)\n"
        "- 식당명 (서울 송파구 테스트로 1) ⭐부모님 운영\n"
        "※ 야구장 내부 식당\n",
        encoding="utf-8",
    )

    rows, _ = parse_markdown(source, "jamsil")

    assert rows[0]["recommendationNote"] == (
        "통역 · 선수단 공통 · 부모님 운영 · 야구장 내부 식당"
    )


def test_review_row_marks_only_fields_that_need_manual_review() -> None:
    place = Place(
        place_id="kakao_123",
        name="선수 추천 식당",
        category="RESTAURANT",
        latitude=37.5,
        longitude=127.0,
        address="서울 송파구",
        telephone="02-123-4567",
        source=PlaceSource.KAKAO,
        source_content_id="123",
        kakao_place_id="123",
        place_url="https://place.map.kakao.com/123",
    )
    prepared = _prepare_snapshot(
        place,
        player_name="테스트",
        recommendation_note=None,
    )
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    document = PlayerPickDocument(
        stadium_id="jamsil",
        player_name="테스트",
        place_id=prepared.place_id,
        place_snapshot=prepared,
        created_at=now,
        updated_at=now,
    )

    review = _review_row(document)

    assert review["placeSnapshot"]["overview"] == (
        "테스트 선수가 추천한 선수 추천 식당입니다."
    )
    assert review["placeSnapshot"]["placeUrl"].endswith("/123")
    assert "telephone" not in review["review"]["missingFields"]
    assert "businessHoursRules" in review["review"]["missingFields"]

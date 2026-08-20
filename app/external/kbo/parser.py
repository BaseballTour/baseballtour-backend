import re
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from typing import Any
from zoneinfo import ZoneInfo

from app.external.kbo.models import (
    KboScheduleGame,
    KboScheduleParseResult,
)
from app.schemas.game import GameStatus


KOREA_TIMEZONE = ZoneInfo("Asia/Seoul")

TEAM_ID_BY_NAME = {
    "두산": "doosan",
    "LG": "lg",
    "키움": "kiwoom",
    "SSG": "ssg",
    "KT": "kt",
    "한화": "hanwha",
    "KIA": "kia",
    "삼성": "samsung",
    "롯데": "lotte",
    "NC": "nc",
}

STADIUM_ID_BY_NAME = {
    "잠실": "jamsil",
    "고척": "gocheok",
    "문학": "incheon",
    "인천": "incheon",
    "수원": "suwon",
    "대전": "daejeon",
    "광주": "gwangju",
    "대구": "daegu",
    "사직": "sajik",
    "창원": "changwon",
}

DATE_PATTERN = re.compile(r"(?P<month>\d{2})\.(?P<day>\d{2})")
TIME_PATTERN = re.compile(r"(?P<hour>\d{1,2}):(?P<minute>\d{2})")
SCORE_PATTERN = re.compile(
    r'<span class="(?:win|lose|same)">(\d+)</span>'
)
TEAM_PATTERN = re.compile(r"<span>([^<]+)</span>")


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _plain_text(value: Any) -> str:
    parser = _TextExtractor()
    parser.feed(unescape(str(value or "")))
    return " ".join("".join(parser.parts).split())


def _cell_text(cell: dict[str, Any]) -> str:
    return str(cell.get("Text") or "")


def _find_cell(
    cells: list[dict[str, Any]],
    class_name: str,
) -> dict[str, Any] | None:
    return next(
        (
            cell
            for cell in cells
            if str(cell.get("Class") or "") == class_name
        ),
        None,
    )


def _status_and_result(
    note: str,
    scores: list[int],
    away_name: str,
    home_name: str,
) -> tuple[GameStatus, int | None, int | None, str | None]:
    if "취소" in note:
        return GameStatus.CANCELLED, None, None, note
    if "연기" in note or "서스펜디드" in note:
        return GameStatus.POSTPONED, None, None, note
    if len(scores) == 2:
        away_score, home_score = scores
        if away_score > home_score:
            result = f"{away_name} 승"
        elif home_score > away_score:
            result = f"{home_name} 승"
        else:
            result = "무승부"
        return GameStatus.COMPLETED, home_score, away_score, result
    if "경기중" in note or "진행중" in note:
        return GameStatus.IN_PROGRESS, None, None, note
    return GameStatus.SCHEDULED, None, None, None


def parse_schedule_response(
    data: dict[str, Any],
    *,
    year: int,
) -> KboScheduleParseResult:
    """KBO 월별 일정 응답을 내부 경기 데이터로 변환한다."""

    rows = data.get("rows")
    if not isinstance(rows, list):
        raise ValueError("KBO 일정 응답에 rows 배열이 없습니다.")

    games: list[KboScheduleGame] = []
    skipped_rows: list[str] = []
    current_month_day: tuple[int, int] | None = None
    occurrence_by_matchup: dict[tuple[Any, ...], int] = {}

    for row_number, row_wrapper in enumerate(rows, start=1):
        raw_cells = (
            row_wrapper.get("row")
            if isinstance(row_wrapper, dict)
            else None
        )
        if not isinstance(raw_cells, list):
            skipped_rows.append(f"row {row_number}: row 배열 없음")
            continue
        cells = [cell for cell in raw_cells if isinstance(cell, dict)]

        day_cell = _find_cell(cells, "day")
        if day_cell is not None:
            match = DATE_PATTERN.search(_plain_text(_cell_text(day_cell)))
            if match is None:
                skipped_rows.append(f"row {row_number}: 날짜 해석 실패")
                current_month_day = None
                continue
            current_month_day = (
                int(match.group("month")),
                int(match.group("day")),
            )

        time_cell = _find_cell(cells, "time")
        play_cell = _find_cell(cells, "play")
        if current_month_day is None or time_cell is None or play_cell is None:
            skipped_rows.append(f"row {row_number}: 필수 셀 없음")
            continue

        time_match = TIME_PATTERN.search(_plain_text(_cell_text(time_cell)))
        team_names = [
            name.strip()
            for name in TEAM_PATTERN.findall(_cell_text(play_cell))
            if name.strip() and name.strip().lower() != "vs"
        ]
        if time_match is None or len(team_names) != 2:
            skipped_rows.append(f"row {row_number}: 시간 또는 팀 해석 실패")
            continue

        away_name, home_name = team_names
        away_team_id = TEAM_ID_BY_NAME.get(away_name)
        home_team_id = TEAM_ID_BY_NAME.get(home_name)
        stadium_name = _plain_text(_cell_text(cells[-2])) if len(cells) >= 2 else ""
        stadium_id = STADIUM_ID_BY_NAME.get(stadium_name)
        if away_team_id is None or home_team_id is None or stadium_id is None:
            skipped_rows.append(
                f"row {row_number}: 미지원 팀/구장 "
                f"({away_name} vs {home_name}, {stadium_name})"
            )
            continue

        note = _plain_text(_cell_text(cells[-1])) if cells else ""
        note = "" if note == "-" else note
        scores = [
            int(value)
            for value in SCORE_PATTERN.findall(_cell_text(play_cell))
        ]
        status, home_score, away_score, result_text = _status_and_result(
            note,
            scores,
            away_name,
            home_name,
        )

        month, day = current_month_day
        game_start_at = datetime(
            year,
            month,
            day,
            int(time_match.group("hour")),
            int(time_match.group("minute")),
            tzinfo=KOREA_TIMEZONE,
        )
        matchup_key = (
            game_start_at.date(),
            away_team_id,
            home_team_id,
            stadium_id,
        )
        occurrence = occurrence_by_matchup.get(matchup_key, 0) + 1
        occurrence_by_matchup[matchup_key] = occurrence
        game_id = (
            f"kbo_{game_start_at:%Y%m%d}_{away_team_id}_"
            f"{home_team_id}_{stadium_id}_{occurrence}"
        )

        games.append(
            KboScheduleGame(
                game_id=game_id,
                home_team_id=home_team_id,
                away_team_id=away_team_id,
                stadium_id=stadium_id,
                game_start_at=game_start_at,
                status=status,
                home_score=home_score,
                away_score=away_score,
                result_text=result_text,
            )
        )

    return KboScheduleParseResult(
        games=games,
        skipped_rows=skipped_rows,
    )

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


def parse_day_games_response(data: dict[str, Any]) -> KboScheduleParseResult:
    """일별 경기 응답을 상태 갱신용 내부 경기 데이터로 변환한다.

    진행 중 점수는 의도적으로 저장하지 않고, GAME_RESULT_CK가 완료를
    나타낼 때만 최종 점수와 승리팀을 반영한다.
    """
    rows = data.get("game")
    if not isinstance(rows, list):
        raise ValueError("KBO 일별 경기 응답에 game 배열이 없습니다.")

    games: list[KboScheduleGame] = []
    skipped_rows: list[str] = []
    occurrence_by_matchup: dict[tuple[Any, ...], int] = {}

    for row_number, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            skipped_rows.append(f"row {row_number}: 객체가 아님")
            continue
        try:
            date_text = str(row["G_DT"])
            time_text = str(row["G_TM"])
            away_name = str(row["AWAY_NM"]).strip()
            home_name = str(row["HOME_NM"]).strip()
            stadium_name = str(row["S_NM"]).strip()
            game_start_at = datetime.strptime(
                f"{date_text}{time_text}",
                "%Y%m%d%H:%M",
            ).replace(tzinfo=KOREA_TIMEZONE)
        except (KeyError, TypeError, ValueError):
            skipped_rows.append(f"row {row_number}: 필수 값 해석 실패")
            continue

        away_team_id = TEAM_ID_BY_NAME.get(away_name)
        home_team_id = TEAM_ID_BY_NAME.get(home_name)
        stadium_id = STADIUM_ID_BY_NAME.get(stadium_name)
        if away_team_id is None or home_team_id is None or stadium_id is None:
            skipped_rows.append(
                f"row {row_number}: 미지원 팀/구장 "
                f"({away_name} vs {home_name}, {stadium_name})"
            )
            continue

        matchup_key = (
            game_start_at.date(),
            away_team_id,
            home_team_id,
            stadium_id,
        )
        occurrence = occurrence_by_matchup.get(matchup_key, 0) + 1
        occurrence_by_matchup[matchup_key] = occurrence
        header_number = int(row.get("HEADER_NO") or 0)
        game_ordinal = header_number if header_number > 0 else occurrence
        game_id = (
            f"kbo_{game_start_at:%Y%m%d}_{away_team_id}_"
            f"{home_team_id}_{stadium_id}_{game_ordinal}"
        )

        cancel_name = str(row.get("CANCEL_SC_NM") or "").strip()
        cancel_code = str(row.get("CANCEL_SC_ID") or "0").strip()
        result_complete = str(row.get("GAME_RESULT_CK") or "0") == "1"
        game_state = str(row.get("GAME_STATE_SC") or "").strip()
        home_score: int | None = None
        away_score: int | None = None
        result_text: str | None = None

        if "연기" in cancel_name or "서스펜디드" in cancel_name:
            status = GameStatus.POSTPONED
            result_text = cancel_name
        elif cancel_code != "0" or "취소" in cancel_name:
            status = GameStatus.CANCELLED
            result_text = cancel_name or "경기 취소"
        elif result_complete:
            status = GameStatus.COMPLETED
            try:
                away_score = int(row.get("T_SCORE_CN"))
                home_score = int(row.get("B_SCORE_CN"))
            except (TypeError, ValueError):
                skipped_rows.append(f"row {row_number}: 최종 점수 해석 실패")
                continue
            if away_score > home_score:
                result_text = f"{away_name} 승"
            elif home_score > away_score:
                result_text = f"{home_name} 승"
            else:
                result_text = "무승부"
        elif game_state == "2":
            status = GameStatus.IN_PROGRESS
        else:
            status = GameStatus.SCHEDULED

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

    return KboScheduleParseResult(games=games, skipped_rows=skipped_rows)

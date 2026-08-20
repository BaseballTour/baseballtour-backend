from dataclasses import dataclass
from datetime import datetime

from app.schemas.game import GameStatus


@dataclass(frozen=True)
class KboScheduleGame:
    """KBO 일정 응답을 정규화한 경기 한 건."""

    game_id: str
    home_team_id: str
    away_team_id: str
    stadium_id: str
    game_start_at: datetime
    status: GameStatus
    home_score: int | None = None
    away_score: int | None = None
    result_text: str | None = None


@dataclass(frozen=True)
class KboScheduleParseResult:
    games: list[KboScheduleGame]
    skipped_rows: list[str]

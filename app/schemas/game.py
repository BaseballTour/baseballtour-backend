from enum import Enum

from pydantic import AwareDatetime, ConfigDict, Field, model_validator

from app.schemas.base import ApiModel
from app.schemas.stadium import StadiumSummaryResponse


class GameStatus(str, Enum):
    """경기 진행 상태."""

    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    POSTPONED = "POSTPONED"


class GameDocument(ApiModel):
    """Firestore games 문서에 저장되는 필드."""

    home_team_id: str = Field(
        min_length=1,
        description="홈 구단 ID",
    )
    away_team_id: str = Field(
        min_length=1,
        description="원정 구단 ID",
    )
    stadium_id: str = Field(
        min_length=1,
        description="경기 구장 ID",
    )
    game_start_at: AwareDatetime

    status: GameStatus = GameStatus.SCHEDULED

    home_score: int | None = Field(
        default=None,
        ge=0,
    )
    away_score: int | None = Field(
        default=None,
        ge=0,
    )
    result_text: str | None = None

    created_at: AwareDatetime
    updated_at: AwareDatetime

    @model_validator(mode="after")
    def validate_different_teams(self) -> "GameDocument":
        if self.home_team_id == self.away_team_id:
            raise ValueError(
                "홈팀과 원정팀은 같을 수 없습니다."
            )

        return self


class GameRecord(GameDocument):
    """Firestore에서 조회한 경기 문서."""

    game_id: str


class GameTeamSummaryResponse(ApiModel):
    """경기 응답에 포함되는 구단 요약 정보."""

    team_id: str
    name: str
    logo_url: str | None = None


class GameResponse(ApiModel):
    """경기 목록 및 상세 조회 응답."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "gameId": "dev_game_20260815_lotte_doosan",
                    "gameStartAt": "2026-08-15T18:00:00+09:00",
                    "status": "SCHEDULED",
                    "homeTeam": {
                        "teamId": "lotte",
                        "name": "롯데 자이언츠",
                        "logoUrl": "https://example.com/teams/lotte.png",
                    },
                    "awayTeam": {
                        "teamId": "doosan",
                        "name": "두산 베어스",
                        "logoUrl": "https://example.com/teams/doosan.png",
                    },
                    "stadium": {
                        "stadiumId": "sajik",
                        "name": "사직야구장",
                        "address": "부산광역시 동래구 사직로 45",
                        "latitude": 35.194,
                        "longitude": 129.0615,
                    },
                    "homeScore": None,
                    "awayScore": None,
                    "resultText": None,
                }
            ]
        }
    )

    game_id: str
    game_start_at: AwareDatetime
    status: GameStatus

    home_team: GameTeamSummaryResponse
    away_team: GameTeamSummaryResponse
    stadium: StadiumSummaryResponse

    home_score: int | None = None
    away_score: int | None = None
    result_text: str | None = None

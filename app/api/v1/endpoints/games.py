from datetime import date
from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.schemas.game import (
    GameResponse,
    GameStatus,
)
from app.schemas.response import (
    ListMeta,
    ListSuccessResponse,
    SuccessResponse,
)
from app.services.game_service import GameService


router = APIRouter(
    prefix="/games",
)


@router.get(
    "",
    response_model=ListSuccessResponse[GameResponse],
    summary="KBO 경기 목록 조회",
    description=(
        "날짜, 구단, 구장, 경기 상태 조건으로 "
        "KBO 경기 목록을 조회합니다."
    ),
)
def get_games(
    game_date: date | None = Query(
        default=None,
        alias="date",
        description="한국시간 기준 경기 날짜",
    ),
    team_id: str | None = Query(
        default=None,
        alias="teamId",
        description="홈팀 또는 원정팀 구단 ID",
    ),
    stadium_id: str | None = Query(
        default=None,
        alias="stadiumId",
        description="구장 ID",
    ),
    game_status: GameStatus | None = Query(
        default=None,
        alias="status",
        description="경기 진행 상태",
    ),
) -> ListSuccessResponse[GameResponse]:
    service = GameService()

    games = service.get_games(
        game_date=game_date,
        team_id=team_id,
        stadium_id=stadium_id,
        game_status=game_status,
    )

    return ListSuccessResponse(
        data=games,
        meta=ListMeta(
            count=len(games),
            next_page_token=None,
        ),
    )


@router.get(
    "/{gameId}",
    response_model=SuccessResponse[GameResponse],
    summary="KBO 경기 상세 조회",
    description="경기 ID로 KBO 경기 상세정보를 조회합니다.",
)
def get_game(
    game_id: Annotated[
        str,
        Path(
            alias="gameId",
            description="경기 ID",
        ),
    ],
) -> SuccessResponse[GameResponse]:
    service = GameService()
    game = service.get_game(game_id)

    return SuccessResponse(data=game)

from fastapi import APIRouter

from app.schemas.response import ListMeta, ListSuccessResponse
from app.schemas.team import TeamResponse
from app.services.team_service import TeamService


router = APIRouter(
    prefix="/teams",
)


@router.get(
    "",
    response_model=ListSuccessResponse[TeamResponse],
    summary="KBO 구단 목록 조회",
    description="Firestore에 저장된 KBO 구단 목록을 조회합니다.",
)
def get_teams() -> ListSuccessResponse[TeamResponse]:
    service = TeamService()
    teams = service.get_teams()

    return ListSuccessResponse(
        data=teams,
        meta=ListMeta(
            count=len(teams),
            next_page_token=None,
        ),
    )

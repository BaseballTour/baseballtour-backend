from fastapi import APIRouter

from app.schemas.response import (
    ListMeta,
    ListSuccessResponse,
)
from app.schemas.term import TermResponse
from app.services.term_service import TermService


router = APIRouter(
    prefix="/terms",
)


@router.get(
    "",
    response_model=ListSuccessResponse[TermResponse],
    summary="활성 약관 목록 조회",
    description=(
        "현재 회원가입에 사용되는 활성 약관 목록을 "
        "조회합니다. 인증 없이 사용할 수 있습니다."
    ),
)
def get_terms(
) -> ListSuccessResponse[TermResponse]:
    service = TermService()
    terms = service.get_active_terms()

    return ListSuccessResponse(
        data=terms,
        meta=ListMeta(
            count=len(terms),
        ),
    )

from typing import Annotated

from fastapi import APIRouter, Path

from app.schemas.notice import (
    NoticeDetailResponse,
    NoticeSummaryResponse,
)
from app.schemas.response import (
    ListMeta,
    ListSuccessResponse,
    SuccessResponse,
)
from app.services.notice_service import NoticeService


router = APIRouter(prefix="/notices")


@router.get(
    "",
    response_model=ListSuccessResponse[NoticeSummaryResponse],
    summary="공지사항 목록 조회",
    description="공개된 공지사항을 최신 게시일순으로 조회합니다.",
)
def get_notices() -> ListSuccessResponse[NoticeSummaryResponse]:
    notices = NoticeService().get_notices()

    return ListSuccessResponse(
        data=notices,
        meta=ListMeta(
            count=len(notices),
            next_page_token=None,
        ),
    )


@router.get(
    "/{noticeId}",
    response_model=SuccessResponse[NoticeDetailResponse],
    summary="공지사항 상세 조회",
    description="공지사항 ID로 공개된 공지사항의 본문을 조회합니다.",
)
def get_notice(
    notice_id: Annotated[
        str,
        Path(
            alias="noticeId",
            description="공지사항 ID",
            openapi_examples={
                "default": {"value": "notice_001"}
            },
        ),
    ],
) -> SuccessResponse[NoticeDetailResponse]:
    notice = NoticeService().get_notice(notice_id)
    return SuccessResponse(data=notice)

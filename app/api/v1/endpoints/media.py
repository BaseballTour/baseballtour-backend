from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
)

from app.api.dependencies.auth import (
    get_current_active_user_id,
)
from app.schemas.media import (
    MediaCompleteRequest,
    MediaCompleteResponse,
    MediaUploadUrlRequest,
    MediaUploadUrlResponse,
)
from app.schemas.response import (
    SuccessResponse,
)
from app.services.storage_service import (
    StorageService,
)


router = APIRouter(
    prefix="/media",
)


@router.post(
    "/upload-urls",
    response_model=SuccessResponse[
        MediaUploadUrlResponse
    ],
    summary="미디어 업로드 URL 발급",
    description=(
        "Firebase Storage에 직접 업로드할 수 있는 "
        "15분 유효 V4 PUT signed URL을 발급합니다."
    ),
)
def create_media_upload_url(
    request: MediaUploadUrlRequest,
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> SuccessResponse[MediaUploadUrlResponse]:
    result = StorageService().create_upload_url(
        user_id=user_id,
        request=request,
    )

    return SuccessResponse(
        data=result,
    )


@router.post(
    "/complete",
    response_model=SuccessResponse[
        MediaCompleteResponse
    ],
    summary="미디어 업로드 완료",
    description=(
        "Firebase Storage 직접 업로드 후 호출합니다. "
        "실제 객체 크기와 Content-Type을 검증한 뒤 "
        "프로필 또는 직관 로그에 연결합니다."
    ),
)
def complete_media_upload(
    request: MediaCompleteRequest,
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> SuccessResponse[MediaCompleteResponse]:
    result = StorageService().complete_upload(
        user_id=user_id,
        request=request,
    )

    return SuccessResponse(
        data=result,
    )

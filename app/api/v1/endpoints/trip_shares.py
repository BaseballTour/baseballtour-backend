from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Path,
    Response,
)

from app.api.dependencies.auth import get_current_active_user_id
from app.core.config import settings
from app.schemas.response import SuccessResponse
from app.schemas.trip_share import (
    SharedTripResponse,
    TripShareResponse,
    TripShareRevokeResponse,
)
from app.services.trip_share_service import TripShareService


router = APIRouter()


def build_share_url(token: str) -> str | None:
    """공유 웹 Origin이 설정된 경우 공개 페이지 URL을 반환합니다."""
    origin = settings.share_web_origin.strip().rstrip("/")
    if not origin:
        return None
    return f"{origin}/s/{token}"


@router.post(
    "/trips/{tripId}/share",
    response_model=SuccessResponse[TripShareResponse],
    summary="여행 공유 링크 발급",
    description=(
        "로그인 사용자가 본인의 활성 여행 일정을 공유할 수 있는 "
        "토큰을 발급합니다. 이미 활성 공유가 있으면 같은 토큰을 반환합니다."
    ),
)
def issue_trip_share(
    trip_id: Annotated[
        str,
        Path(alias="tripId", min_length=1),
    ],
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
    response: Response,
) -> SuccessResponse[TripShareResponse]:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    token = TripShareService().issue(
        user_id=user_id,
        trip_id=trip_id,
    )

    return SuccessResponse(
        data=TripShareResponse(
            share_token=token,
            share_url=build_share_url(token),
        )
    )


@router.delete(
    "/trips/{tripId}/share",
    response_model=SuccessResponse[TripShareRevokeResponse],
    summary="여행 공유 해제",
    description=(
        "로그인 사용자가 본인 여행의 공유를 해제합니다. "
        "이미 해제된 경우 revoked=false를 반환합니다."
    ),
)
def revoke_trip_share(
    trip_id: Annotated[
        str,
        Path(alias="tripId", min_length=1),
    ],
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
    response: Response,
) -> SuccessResponse[TripShareRevokeResponse]:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    revoked = TripShareService().revoke(
        user_id=user_id,
        trip_id=trip_id,
    )

    return SuccessResponse(
        data=TripShareRevokeResponse(
            revoked=revoked,
        )
    )


@router.get(
    "/shared-trips/{shareToken}",
    response_model=SuccessResponse[SharedTripResponse],
    summary="공유 여행 조회",
    description=(
        "공유 토큰으로 여행 일정을 조회합니다. "
        "로그인하지 않은 사용자도 조회할 수 있습니다."
    ),
)
def get_shared_trip(
    share_token: Annotated[
        str,
        Path(
            alias="shareToken",
            min_length=20,
            max_length=128,
        ),
    ],
    response: Response,
) -> SuccessResponse[SharedTripResponse]:
    # 공유 해제가 브라우저/CDN 캐시에 가려지지 않도록 캐시하지 않습니다.
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"

    shared_trip = TripShareService().get_public_trip(
        token=share_token,
    )

    return SuccessResponse(data=shared_trip)

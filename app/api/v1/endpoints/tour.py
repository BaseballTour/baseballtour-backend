from typing import Literal

from fastapi import APIRouter, Path, Query

from app.core.exceptions import AppException
from app.external.tour_api.adapter import (
    tour_api_adapter,
)
from app.models.place import Place, PlaceCategory
from app.schemas.response import (
    ListMeta,
    ListSuccessResponse,
    SuccessResponse,
)
from app.services.place_enrichment import (
    enrich_place_with_kakao,
)


router = APIRouter(
    prefix="/tour",
    tags=["TourAPI"],
)


TourNearbyCategory = Literal[
    "TOURIST_SPOT",
    "RESTAURANT",
    "ACCOMMODATION",
    "CULTURAL_FACILITY",
    "SHOPPING",
    "FESTIVAL",
    "ACTIVITY",
]


def _parse_page_token(
    page_token: str | None,
) -> int:
    if page_token is None:
        return 1

    try:
        page_no = int(page_token)
    except ValueError as exc:
        raise AppException(
            status_code=400,
            code="INVALID_PAGE_TOKEN",
            message=(
                "페이지 토큰 형식이 "
                "올바르지 않습니다."
            ),
        ) from exc

    if page_no < 1:
        raise AppException(
            status_code=400,
            code="INVALID_PAGE_TOKEN",
            message=(
                "페이지 토큰 형식이 "
                "올바르지 않습니다."
            ),
        )

    return page_no


@router.get(
    "/nearby",
    response_model=ListSuccessResponse[Place],
)
async def read_nearby_places(
    longitude: float = Query(
        default=127.0719,
        ge=-180,
        le=180,
        description="경도, TourAPI mapX",
        examples=[127.0719],
    ),
    latitude: float = Query(
        default=37.5122,
        ge=-90,
        le=90,
        description="위도, TourAPI mapY",
        examples=[37.5122],
    ),
    radius: int = Query(
        default=2000,
        ge=1,
        le=20000,
        description="검색 반경, 미터 단위",
        examples=[2000],
    ),
    category: (
        TourNearbyCategory | None
    ) = Query(
        default=None,
        description="내부 장소 카테고리 필터",
        examples=["RESTAURANT"],
    ),
    page_size: int = Query(
        default=20,
        alias="pageSize",
        ge=1,
        description="페이지당 장소 수",
        examples=[20],
    ),
    page_token: str | None = Query(
        default=None,
        alias="pageToken",
        description=(
            "이전 응답의 nextPageToken"
        ),
        examples=["2"],
    ),
) -> ListSuccessResponse[Place]:
    page_no = _parse_page_token(
        page_token
    )

    place_page = (
        await tour_api_adapter
        .get_nearby_place_page(
            longitude=longitude,
            latitude=latitude,
            radius=radius,
            page_no=page_no,
            num_of_rows=page_size,
            category=(
                PlaceCategory(category)
                if category is not None
                else None
            ),
        )
    )

    return ListSuccessResponse(
        data=place_page.places,
        meta=ListMeta(
            count=len(place_page.places),
            next_page_token=(
                place_page.next_page_token
            ),
        ),
    )


@router.get(
    "/places/{placeId}",
    response_model=SuccessResponse[Place],
)
async def read_place_detail(
    place_id: str = Path(
        alias="placeId",
        description=(
            "내부 장소 ID, "
            "예: tour_1603175"
        ),
        examples=["tour_1603175"],
    ),
) -> SuccessResponse[Place]:
    prefix = "tour_"

    if (
        not place_id.startswith(prefix)
        or not place_id[len(prefix):]
    ):
        raise AppException(
            status_code=400,
            code="INVALID_PLACE_ID",
            message=(
                "TourAPI 장소 ID 형식이 "
                "올바르지 않습니다."
            ),
            details={
                "expectedFormat":
                    "tour_{contentId}"
            },
        )

    content_id = place_id[
        len(prefix):
    ]

    place = (
        await tour_api_adapter
        .get_place_detail(
            content_id=content_id,
        )
    )

    place = await enrich_place_with_kakao(
        place
    )

    return SuccessResponse(
        data=place
    )

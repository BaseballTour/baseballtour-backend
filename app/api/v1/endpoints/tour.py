from fastapi import APIRouter, Path, Query

from app.core.exceptions import AppException
from app.models.place import Place
from app.external.tour_api.adapter import tour_api_adapter
from app.services.place_enrichment import enrich_place_with_kakao
from app.schemas.response import (
    ListMeta,
    ListSuccessResponse,
    SuccessResponse,
)

router = APIRouter(
    prefix="/tour",
    tags=["TourAPI"],
)


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
    ),
    latitude: float = Query(
        default=37.5122,
        ge=-90,
        le=90,
        description="위도, TourAPI mapY",
    ),
    radius: int = Query(
        default=2000,
        ge=1,
        le=20000,
        description="검색 반경, 미터 단위",
    ),
) -> ListSuccessResponse[Place]:
    places = await tour_api_adapter.get_nearby_place_list(
        longitude=longitude,
        latitude=latitude,
        radius=radius,
    )

    return ListSuccessResponse(
        data=places,
        meta=ListMeta(
            count=len(places),
            next_page_token=None,
        ),
    )


@router.get(
    "/places/{placeId}",
    response_model=SuccessResponse[Place],
)
async def read_place_detail(
    place_id: str = Path(
        alias="placeId",
        description="내부 장소 ID, 예: tour_1603175",
    ),
) -> SuccessResponse[Place]:
    prefix = "tour_"
    if not place_id.startswith(prefix) or not place_id[len(prefix):]:
        raise AppException(
            status_code=400,
            code="INVALID_PLACE_ID",
            message="TourAPI 장소 ID 형식이 올바르지 않습니다.",
            details={"expectedFormat": "tour_{contentId}"},
        )

    content_id = place_id[len(prefix):]
    place = await tour_api_adapter.get_place_detail(
        content_id=content_id,
    )
    place = await enrich_place_with_kakao(place)
    return SuccessResponse(data=place)

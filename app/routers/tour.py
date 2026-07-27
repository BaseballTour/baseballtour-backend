from fastapi import APIRouter, Query

from app.models.place import Place
from app.services.tour_api import get_nearby_place_list


router = APIRouter(
    prefix="/api/tour",
    tags=["TourAPI"],
)


@router.get(
    "/nearby",
    response_model=list[Place],
)
async def read_nearby_places(
    longitude: float = Query(
        default=127.0719,
        description="경도, TourAPI mapX",
    ),
    latitude: float = Query(
        default=37.5122,
        description="위도, TourAPI mapY",
    ),
    radius: int = Query(
        default=2000,
        ge=1,
        le=20000,
        description="검색 반경, 미터 단위",
    ),
) -> list[Place]:
    return await get_nearby_place_list(
        longitude=longitude,
        latitude=latitude,
        radius=radius,
    )
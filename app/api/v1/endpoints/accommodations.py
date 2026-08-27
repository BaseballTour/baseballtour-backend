from fastapi import APIRouter, Query

from app.core.exceptions import AppException
from app.external.kakao.client import reverse_geocode, search_place_page
from app.external.kakao.mapper import (
    kakao_address_to_accommodation,
    kakao_place_to_accommodation,
)
from app.schemas.accommodation import AccommodationCandidate
from app.schemas.response import ListMeta, ListSuccessResponse, SuccessResponse


router = APIRouter(prefix="/accommodations")


@router.get(
    "/search",
    response_model=ListSuccessResponse[AccommodationCandidate],
    summary="Kakao 숙소 검색",
    description=(
        "Kakao Local에서 숙박(AD5) 장소만 검색합니다. 선택한 후보의 이름·주소·"
        "좌표와 kakaoPlaceId를 여행 accommodation에 복사해 저장합니다."
    ),
)
async def search_accommodations(
    keyword: str = Query(min_length=1, max_length=100, examples=["고척 호텔"]),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    latitude: float | None = Query(default=None, ge=-90, le=90),
    radius: int = Query(default=20_000, ge=0, le=20_000),
    page_size: int = Query(default=15, alias="pageSize", ge=1, le=15),
    page_token: str | None = Query(default=None, alias="pageToken"),
) -> ListSuccessResponse[AccommodationCandidate]:
    if (longitude is None) != (latitude is None):
        raise AppException(
            status_code=400,
            code="ACCOMMODATION_COORDINATES_INCOMPLETE",
            message="longitude와 latitude는 함께 전달해야 합니다.",
        )
    try:
        page = int(page_token or "1")
        if page < 1:
            raise ValueError
    except ValueError as exc:
        raise AppException(
            status_code=400,
            code="PAGE_TOKEN_INVALID",
            message="pageToken은 1 이상의 정수여야 합니다.",
        ) from exc

    result = await search_place_page(
        keyword,
        longitude=longitude,
        latitude=latitude,
        radius=radius,
        page=page,
        size=page_size,
        category_group_code="AD5",
    )
    candidates: list[AccommodationCandidate] = []
    for item in result.documents:
        try:
            candidates.append(kakao_place_to_accommodation(item))
        except (TypeError, ValueError):
            continue
    return ListSuccessResponse(
        data=candidates,
        meta=ListMeta(
            count=len(candidates),
            next_page_token=None if result.is_end else str(page + 1),
        ),
    )


@router.get(
    "/reverse-geocode",
    response_model=SuccessResponse[AccommodationCandidate],
    summary="지도 선택 좌표를 숙소 Anchor 후보로 변환",
    description=(
        "사용자가 지도에서 선택한 좌표를 주소로 변환합니다. 건물명이 없으면 "
        "주소가 name으로 반환되며 프론트에서 숙소 이름을 수정할 수 있습니다."
    ),
)
async def resolve_accommodation_map_point(
    longitude: float = Query(ge=-180, le=180),
    latitude: float = Query(ge=-90, le=90),
) -> SuccessResponse[AccommodationCandidate]:
    documents = await reverse_geocode(
        longitude=longitude,
        latitude=latitude,
    )
    if not documents:
        raise AppException(
            status_code=404,
            code="ACCOMMODATION_ADDRESS_NOT_FOUND",
            message="선택한 좌표의 주소를 찾을 수 없습니다.",
        )
    try:
        candidate = kakao_address_to_accommodation(
            documents[0],
            latitude=latitude,
            longitude=longitude,
        )
    except (TypeError, ValueError) as exc:
        raise AppException(
            status_code=502,
            code="EXTERNAL_API_INVALID_RESPONSE",
            message="Kakao Local 주소 응답을 변환할 수 없습니다.",
        ) from exc
    return SuccessResponse(data=candidate)

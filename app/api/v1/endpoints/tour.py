from typing import Literal

from fastapi import APIRouter, Path, Query

from app.core.exceptions import AppException
from app.api.openapi_responses import TOUR_API_ERROR_RESPONSES
from app.external.tour_api.adapter import (
    tour_api_adapter,
)
from app.external.tour_api.filters import (
    FILTER_DEFINITIONS,
    TourFilterId,
)
from app.models.place import Place, PlaceCategory
from app.schemas.player_pick import PlayerPickResponse
from app.schemas.response import (
    ListMeta,
    ListSuccessResponse,
    SuccessResponse,
)
from app.schemas.tour import TourClassification, TourFilterOption
from app.services.place_enrichment import (
    enrich_place_with_kakao,
)
from app.services.player_pick_service import PlayerPickService


router = APIRouter(
    prefix="/tour",
    tags=["TourAPI"],
    responses=TOUR_API_ERROR_RESPONSES,
)


TourNearbyCategory = Literal[
    "TOURIST_SPOT",
    "RESTAURANT",
    "CAFE",
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


def _validate_lcls_filters(
    lcls_system1: str | None,
    lcls_system2: str | None,
    lcls_system3: str | None,
) -> None:
    if lcls_system2 is not None and lcls_system1 is None:
        raise AppException(
            status_code=400,
            code="INVALID_CLASSIFICATION_FILTER",
            message="신분류 중분류 검색에는 대분류 코드가 필요합니다.",
        )
    if lcls_system3 is not None and (
        lcls_system1 is None or lcls_system2 is None
    ):
        raise AppException(
            status_code=400,
            code="INVALID_CLASSIFICATION_FILTER",
            message="신분류 소분류 검색에는 대분류와 중분류 코드가 필요합니다.",
        )


def _validate_filter_contract(
    filter_id: TourFilterId | None,
    *,
    category: str | None = None,
    lcls_system1: str | None = None,
    lcls_system2: str | None = None,
    lcls_system3: str | None = None,
) -> None:
    if filter_id is None:
        return
    if any(
        value is not None
        for value in (
            category,
            lcls_system1,
            lcls_system2,
            lcls_system3,
        )
    ):
        raise AppException(
            status_code=400,
            code="FILTER_CONFLICT",
            message=(
                "filterId는 category 또는 TourAPI 신분류 코드와 "
                "함께 사용할 수 없습니다."
            ),
        )


@router.get(
    "/filter-options",
    response_model=ListSuccessResponse[TourFilterOption],
    summary="프론트 검색 필터 목록 조회",
)
async def read_filter_options() -> ListSuccessResponse[TourFilterOption]:
    options = [
        TourFilterOption(
            filter_id=filter_id.value,
            label=definition.label,
            group=definition.group,
            classification_codes=[
                clause.lcls_system3
                or clause.lcls_system2
                or clause.lcls_system1
                for clause in definition.clauses
            ],
        )
        for filter_id, definition in FILTER_DEFINITIONS.items()
    ]
    return ListSuccessResponse(
        data=options,
        meta=ListMeta(count=len(options), next_page_token=None),
    )


@router.get(
    "/player-picks",
    response_model=ListSuccessResponse[PlayerPickResponse],
    summary="구장·선수별 추천 장소 조회",
)
async def read_player_picks(
    stadium_id: str = Query(alias="stadiumId", min_length=1),
    player_name: str | None = Query(
        default=None,
        alias="playerName",
        min_length=1,
    ),
) -> ListSuccessResponse[PlayerPickResponse]:
    picks = await PlayerPickService().get_player_picks(
        stadium_id=stadium_id,
        player_name=player_name,
    )
    return ListSuccessResponse(
        data=picks,
        meta=ListMeta(count=len(picks), next_page_token=None),
    )


@router.get(
    "/classifications",
    response_model=ListSuccessResponse[TourClassification],
    summary="TourAPI 신분류 코드 목록 조회",
)
async def read_classifications(
    lcls_system1: str | None = Query(
        default=None,
        alias="lclsSystem1",
        pattern=r"^[A-Z]{2}$",
    ),
    lcls_system2: str | None = Query(
        default=None,
        alias="lclsSystem2",
        pattern=r"^[A-Z]{2}[0-9]{2}$",
    ),
    lcls_system3: str | None = Query(
        default=None,
        alias="lclsSystem3",
        pattern=r"^[A-Z]{2}[0-9]{6}$",
    ),
    page_size: int = Query(
        default=100,
        alias="pageSize",
        ge=1,
        le=1000,
    ),
    page_token: str | None = Query(
        default=None,
        alias="pageToken",
    ),
) -> ListSuccessResponse[TourClassification]:
    _validate_lcls_filters(
        lcls_system1,
        lcls_system2,
        lcls_system3,
    )
    page = await tour_api_adapter.get_classification_page(
        page_no=_parse_page_token(page_token),
        num_of_rows=page_size,
        lcls_system1=lcls_system1,
        lcls_system2=lcls_system2,
        lcls_system3=lcls_system3,
    )
    return ListSuccessResponse(
        data=page.classifications,
        meta=ListMeta(
            count=len(page.classifications),
            next_page_token=page.next_page_token,
        ),
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
    filter_id: TourFilterId | None = Query(
        default=None,
        alias="filterId",
        description="프론트 통합 필터 ID",
        examples=["CAFE"],
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
    _validate_filter_contract(filter_id, category=category)
    page_no = _parse_page_token(
        page_token
    )

    if filter_id is not None:
        place_page = await tour_api_adapter.get_nearby_place_page_by_filter(
            filter_id=filter_id,
            longitude=longitude,
            latitude=latitude,
            radius=radius,
            page_no=page_no,
            num_of_rows=page_size,
        )
    else:
        place_page = await tour_api_adapter.get_nearby_place_page(
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


@router.get(
    "/search",
    response_model=ListSuccessResponse[Place],
    summary="관광 장소 키워드 검색",
)
async def search_places(
    keyword: str = Query(min_length=1, max_length=100, examples=["잠실 맛집"]),
    category: TourNearbyCategory | None = Query(default=None),
    filter_id: TourFilterId | None = Query(
        default=None,
        alias="filterId",
        description="프론트 통합 필터 ID",
        examples=["JAPANESE"],
    ),
    lcls_system1: str | None = Query(
        default=None,
        alias="lclsSystem1",
        min_length=2,
        max_length=2,
        pattern=r"^[A-Z]{2}$",
        description="TourAPI 신분류 대분류 코드",
        examples=["FD"],
    ),
    lcls_system2: str | None = Query(
        default=None,
        alias="lclsSystem2",
        min_length=4,
        max_length=4,
        pattern=r"^[A-Z]{2}[0-9]{2}$",
        description="TourAPI 신분류 중분류 코드",
        examples=["FD02"],
    ),
    lcls_system3: str | None = Query(
        default=None,
        alias="lclsSystem3",
        min_length=8,
        max_length=8,
        pattern=r"^[A-Z]{2}[0-9]{6}$",
        description="TourAPI 신분류 소분류 코드",
        examples=["FD020200"],
    ),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
    page_token: str | None = Query(default=None, alias="pageToken"),
) -> ListSuccessResponse[Place]:
    _validate_filter_contract(
        filter_id,
        category=category,
        lcls_system1=lcls_system1,
        lcls_system2=lcls_system2,
        lcls_system3=lcls_system3,
    )
    _validate_lcls_filters(
        lcls_system1,
        lcls_system2,
        lcls_system3,
    )
    if filter_id is not None:
        page = await tour_api_adapter.search_place_page_by_filter(
            filter_id=filter_id,
            keyword=keyword,
            page_no=_parse_page_token(page_token),
            num_of_rows=page_size,
        )
    else:
        page = await tour_api_adapter.search_place_page(
            keyword=keyword,
            category=PlaceCategory(category) if category is not None else None,
            lcls_system1=lcls_system1,
            lcls_system2=lcls_system2,
            lcls_system3=lcls_system3,
            page_no=_parse_page_token(page_token),
            num_of_rows=page_size,
        )
    return ListSuccessResponse(
        data=page.places,
        meta=ListMeta(
            count=len(page.places),
            next_page_token=page.next_page_token,
        ),
    )

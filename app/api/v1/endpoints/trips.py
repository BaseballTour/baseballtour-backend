from datetime import date
from typing import Annotated, Literal

from fastapi import (
    APIRouter,
    Depends,
    Header,
    Path,
    Query,
    Response,
    status,
)

from app.api.dependencies.auth import get_current_active_user_id
from app.api.openapi_responses import TRIP_ERROR_RESPONSES
from app.core.exceptions import AppException
from app.core.time import to_korea_datetime
from app.external.tour_api.filters import FILTER_DEFINITIONS, TourFilterId
from app.models.place import Place, PlaceCategory
from app.schemas.itinerary_plan import (
    ItineraryPlanAddItemRequest,
    ItineraryPlanFixedRequest,
    ItineraryPlanRecord,
    ItineraryPlanReorderRequest,
    ItineraryPlanResponse,
    ItineraryPlanTimeUpdateRequest,
)
from app.schemas.place_selection import (
    PlaceSelectionCreateRequest,
    PlaceSelectionImportRequest,
    PlaceSelectionRecord,
    PlaceSelectionResponse,
    PlaceSelectionUpdateRequest,
)
from app.schemas.response import (
    ListMeta,
    ListSuccessResponse,
    SuccessResponse,
)
from app.schemas.trip import (
    TripCreateRequest,
    TripDetailResponse,
    TripRecord,
    TripSummaryResponse,
    TripUpdateRequest,
)
from app.services.itinerary_generation_service import (
    ItineraryGenerationService,
)
from app.services.itinerary_plan_service import (
    ItineraryPlanService,
)
from app.services.place_selection_service import (
    PlaceSelectionService,
)
from app.services.trip_service import TripService
from app.services.storage_service import StorageService


router = APIRouter(
    prefix="/trips",
    responses=TRIP_ERROR_RESPONSES,
)


RecommendationSort = Literal["RECOMMENDED", "DISTANCE", "NAME"]

_TOP_LEVEL_FILTER_CATEGORIES = {
    TourFilterId.RESTAURANT: PlaceCategory.RESTAURANT,
    TourFilterId.CAFE: PlaceCategory.CAFE,
    TourFilterId.ACTIVITY: PlaceCategory.ACTIVITY,
    TourFilterId.TOURISM: PlaceCategory.TOURIST_SPOT,
    TourFilterId.FESTIVAL: PlaceCategory.FESTIVAL,
    TourFilterId.EXHIBITION: PlaceCategory.CULTURAL_FACILITY,
    TourFilterId.SHOPPING: PlaceCategory.SHOPPING,
}


def _matches_recommendation_filter(place: Place, filter_id: str) -> bool:
    if filter_id == "PLAYER_PICK":
        return place.is_player_pick
    try:
        parsed = TourFilterId(filter_id)
    except ValueError as exc:
        raise AppException(
            status_code=400,
            code="INVALID_RECOMMENDATION_FILTER",
            message="지원하지 않는 추천 장소 필터입니다.",
            details={"filterId": filter_id},
        ) from exc

    fallback_category = _TOP_LEVEL_FILTER_CATEGORIES.get(parsed)
    if fallback_category is not None and place.category == fallback_category:
        return True
    definition = FILTER_DEFINITIONS[parsed]
    if definition.allowed_categories and place.category in definition.allowed_categories:
        return True
    return any(
        place.lcls_system1 == clause.lcls_system1
        and (clause.lcls_system2 is None or place.lcls_system2 == clause.lcls_system2)
        and (clause.lcls_system3 is None or place.lcls_system3 == clause.lcls_system3)
        for clause in definition.clauses
    )


def _recommendation_page_number(page_token: str | None) -> int:
    try:
        page_number = int(page_token or "1")
    except ValueError as exc:
        raise AppException(
            status_code=400,
            code="INVALID_PAGE_TOKEN",
            message="페이지 토큰 형식이 올바르지 않습니다.",
        ) from exc
    if page_number < 1:
        raise AppException(
            status_code=400,
            code="INVALID_PAGE_TOKEN",
            message="페이지 토큰 형식이 올바르지 않습니다.",
        )
    return page_number


def resolve_trip_subtitle(
    trip: TripRecord,
) -> str:
    """사용자 부제목이 없으면 여행 날짜를 반환합니다."""

    if trip.subtitle:
        return trip.subtitle

    start_date = to_korea_datetime(
        trip.trip_start_at
    ).date()
    end_date = to_korea_datetime(
        trip.trip_end_at
    ).date()

    start_text = start_date.strftime("%Y.%m.%d")

    if start_date == end_date:
        return start_text

    end_text = end_date.strftime("%Y.%m.%d")

    return f"{start_text} ~ {end_text}"


def resolve_trip_cover_image_url(
    trip: TripRecord,
) -> str | None:
    path = trip.cover_image_storage_path
    if not path:
        return None
    return StorageService().create_download_url(path)


def to_summary_response(
    trip: TripRecord,
) -> TripSummaryResponse:
    """TripRecord를 외부 공개용 요약 응답으로 변환합니다."""

    return TripSummaryResponse(
        trip_id=trip.trip_id,
        game_id=trip.game_id,
        title=trip.title,
        subtitle=resolve_trip_subtitle(trip),
        cover_image_url=resolve_trip_cover_image_url(trip),
        status=trip.status,
        trip_start_at=trip.trip_start_at,
        trip_end_at=trip.trip_end_at,
        created_at=trip.created_at,
    )


def to_itinerary_plan_response(
    plan: ItineraryPlanRecord,
) -> ItineraryPlanResponse:
    """저장된 일정 Plan을 API 응답으로 변환합니다."""

    return ItineraryPlanResponse(
        plan_id=plan.plan_id,
        trip_id=plan.trip_id,
        status=plan.status,
        algorithm_version=plan.algorithm_version,
        total_travel_minutes=plan.total_travel_minutes,
        total_travel_distance_meters=(
            plan.total_travel_distance_meters
        ),
        days=plan.days,
        excluded_places=plan.excluded_places,
        recommendation_summary=plan.recommendation_summary,
    )


def to_place_selection_response(
    selection: PlaceSelectionRecord,
) -> PlaceSelectionResponse:
    """장소 선택 저장 모델을 외부 응답으로 변환합니다."""

    return PlaceSelectionResponse(
        place_id=selection.place_id,
        is_required=selection.is_required,
        created_at=selection.created_at,
    )


def to_detail_response(
    trip: TripRecord,
) -> TripDetailResponse:
    """TripRecord를 외부 공개용 상세 응답으로 변환합니다."""

    return TripDetailResponse(
        trip_id=trip.trip_id,
        game_id=trip.game_id,
        title=trip.title,
        subtitle=resolve_trip_subtitle(trip),
        cover_image_url=resolve_trip_cover_image_url(trip),
        status=trip.status,
        trip_start_at=trip.trip_start_at,
        trip_end_at=trip.trip_end_at,
        created_at=trip.created_at,
        arrival_point=trip.arrival_point,
        departure_point=trip.departure_point,
        accommodation=trip.accommodation,
        schedule_density=trip.schedule_density,
        preferred_categories=trip.preferred_categories,
        active_plan_id=trip.active_plan_id,
        updated_at=trip.updated_at,
    )


@router.post(
    "",
    response_model=SuccessResponse[TripSummaryResponse],
    status_code=status.HTTP_201_CREATED,
    summary="여행 생성",
    description=(
        "경기와 여행 기본정보를 저장하고 "
        "로그인 사용자의 여행을 생성합니다."
    ),
)
def create_trip(
    request: TripCreateRequest,
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
    idempotency_key: Annotated[
        str,
        Header(
            alias="Idempotency-Key",
            min_length=1,
            max_length=128,
            description=(
                "여행 생성 요청 재시도 시 동일하게 사용하는 고유 키"
            ),
        ),
    ],
) -> SuccessResponse[TripSummaryResponse]:
    service = TripService()

    trip = service.create_trip(
        user_id=user_id,
        request=request,
        idempotency_key=idempotency_key,
    )

    return SuccessResponse(
        data=to_summary_response(trip)
    )


@router.get(
    "",
    response_model=ListSuccessResponse[TripSummaryResponse],
    summary="내 여행 목록 조회",
    description=(
        "로그인 사용자가 소유한 여행 중 일정 생성이 완료된 여행을 조회합니다. "
        "최초 일정 생성 전 또는 생성 도중인 미완성 여행은 반환하지 않습니다."
    ),
)
def get_my_trips(
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> ListSuccessResponse[TripSummaryResponse]:
    service = TripService()

    trips = service.get_my_trips(
        user_id=user_id,
    )

    data = [
        to_summary_response(trip)
        for trip in trips
    ]

    return ListSuccessResponse(
        data=data,
        meta=ListMeta(
            count=len(data),
            next_page_token=None,
        ),
    )


@router.get(
    "/{tripId}",
    response_model=SuccessResponse[TripDetailResponse],
    summary="여행 상세 조회",
    description=(
        "로그인 사용자가 소유한 여행의 "
        "기본정보를 조회합니다."
    ),
)
def get_trip(
    trip_id: Annotated[
        str,
        Path(
            alias="tripId",
            description="여행 ID",
        ),
    ],
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> SuccessResponse[TripDetailResponse]:
    service = TripService()

    trip = service.get_trip(
        user_id=user_id,
        trip_id=trip_id,
    )

    return SuccessResponse(
        data=to_detail_response(trip)
    )


@router.patch(
    "/{tripId}",
    response_model=SuccessResponse[TripDetailResponse],
    summary="여행 기본정보 수정",
    description=(
        "로그인 사용자가 소유한 여행의 "
        "경기, 시간, 장소, 숙소 정보를 수정합니다."
    ),
)
def update_trip(
    trip_id: Annotated[
        str,
        Path(
            alias="tripId",
            description="여행 ID",
        ),
    ],
    request: TripUpdateRequest,
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> SuccessResponse[TripDetailResponse]:
    service = TripService()

    trip = service.update_trip(
        user_id=user_id,
        trip_id=trip_id,
        request=request,
    )

    return SuccessResponse(
        data=to_detail_response(trip)
    )


@router.delete(
    "/{tripId}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="여행 삭제",
    description="로그인 사용자가 소유한 여행을 삭제합니다.",
)
def delete_trip(
    trip_id: Annotated[
        str,
        Path(
            alias="tripId",
            description="여행 ID",
        ),
    ],
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> Response:
    service = TripService()

    service.delete_trip(
        user_id=user_id,
        trip_id=trip_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )



@router.post(
    "/{tripId}/place-selections",
    response_model=SuccessResponse[PlaceSelectionResponse],
    status_code=status.HTTP_201_CREATED,
    summary="여행 장소 선택 추가",
    description=(
        "로그인 사용자가 소유한 여행에 "
        "방문할 장소를 추가합니다."
    ),
)
def create_place_selection(
    trip_id: Annotated[
        str,
        Path(
            alias="tripId",
            description="여행 ID",
        ),
    ],
    request: PlaceSelectionCreateRequest,
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> SuccessResponse[PlaceSelectionResponse]:
    service = PlaceSelectionService()

    selection = service.create_selection(
        user_id=user_id,
        trip_id=trip_id,
        request=request,
    )

    return SuccessResponse(
        data=to_place_selection_response(selection)
    )


@router.get(
    "/{tripId}/place-selections",
    response_model=ListSuccessResponse[PlaceSelectionResponse],
    summary="여행 장소 선택 목록 조회",
    description=(
        "로그인 사용자가 소유한 여행에 "
        "선택된 장소 목록을 조회합니다."
    ),
)
def get_place_selections(
    trip_id: Annotated[
        str,
        Path(
            alias="tripId",
            description="여행 ID",
        ),
    ],
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> ListSuccessResponse[PlaceSelectionResponse]:
    service = PlaceSelectionService()

    selections = service.get_selections(
        user_id=user_id,
        trip_id=trip_id,
    )

    data = [
        to_place_selection_response(selection)
        for selection in selections
    ]

    return ListSuccessResponse(
        data=data,
        meta=ListMeta(
            count=len(data),
            next_page_token=None,
        ),
    )


@router.post(
    "/{tripId}/place-selections/import",
    response_model=ListSuccessResponse[PlaceSelectionResponse],
    summary="개인 찜 컬렉션에서 여행 후보 불러오기",
    description=(
        "개인 찜 컬렉션에서 현재 경기장과 같은 지역의 "
        "장소만 여행 후보로 불러옵니다. "
        "이미 선택된 장소는 중복 생성하지 않습니다."
    ),
)
async def import_place_selections(
    trip_id: Annotated[
        str,
        Path(
            alias="tripId",
            description="여행 ID",
        ),
    ],
    request: PlaceSelectionImportRequest,
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> ListSuccessResponse[PlaceSelectionResponse]:
    service = PlaceSelectionService()

    selections = await service.import_from_favorite_collection(
        user_id=user_id,
        trip_id=trip_id,
        collection_id=request.collection_id,
    )

    data = [
        to_place_selection_response(selection)
        for selection in selections
    ]

    return ListSuccessResponse(
        data=data,
        meta=ListMeta(
            count=len(data),
            next_page_token=None,
        ),
    )


@router.patch(
    "/{tripId}/place-selections/{placeId}",
    response_model=SuccessResponse[PlaceSelectionResponse],
    summary="여행 후보 필수 방문 여부 변경",
    description=(
        "선택된 여행 후보의 isRequired 값을 변경합니다."
    ),
)
def update_place_selection_required(
    trip_id: Annotated[
        str,
        Path(
            alias="tripId",
            description="여행 ID",
        ),
    ],
    place_id: Annotated[
        str,
        Path(
            alias="placeId",
            description="선택한 장소 ID",
        ),
    ],
    request: PlaceSelectionUpdateRequest,
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> SuccessResponse[PlaceSelectionResponse]:
    service = PlaceSelectionService()

    selection = service.update_required(
        user_id=user_id,
        trip_id=trip_id,
        place_id=place_id,
        is_required=request.is_required,
    )

    return SuccessResponse(
        data=to_place_selection_response(selection)
    )


@router.delete(
    "/{tripId}/place-selections/{placeId}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="여행 장소 선택 삭제",
    description=(
        "로그인 사용자가 소유한 여행에서 "
        "선택한 장소를 삭제합니다."
    ),
)
def delete_place_selection(
    trip_id: Annotated[
        str,
        Path(
            alias="tripId",
            description="여행 ID",
        ),
    ],
    place_id: Annotated[
        str,
        Path(
            alias="placeId",
            description="선택한 장소 ID",
        ),
    ],
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> Response:
    service = PlaceSelectionService()

    service.delete_selection(
        user_id=user_id,
        trip_id=trip_id,
        place_id=place_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )



@router.get(
    "/{tripId}/recommendation-candidates",
    response_model=ListSuccessResponse[Place],
    summary="일정 생성 전 추천 후보 조회",
    description=(
        "경기장·도착지·출발지·숙소 주변의 TourAPI 및 선수 추천 장소를 "
        "중복 제거 후 반환합니다. keyword·filterId·sort는 전체 후보에 "
        "먼저 적용되며, 그 결과를 pageSize·pageToken으로 나눕니다."
    ),
)
async def get_recommendation_candidates(
    trip_id: Annotated[str, Path(alias="tripId")],
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
    page_size: Annotated[
        int,
        Query(alias="pageSize", ge=1, le=50, description="페이지 크기"),
    ] = 20,
    page_token: Annotated[
        str | None,
        Query(alias="pageToken", description="이전 응답의 nextPageToken"),
    ] = None,
    filter_id: Annotated[
        str | None,
        Query(
            alias="filterId",
            description=(
                "/tour/filter-options의 통합 필터 ID 또는 PLAYER_PICK"
            ),
        ),
    ] = None,
    keyword: Annotated[
        str | None,
        Query(min_length=1, max_length=100, description="후보 이름·주소 검색어"),
    ] = None,
    sort: Annotated[
        RecommendationSort,
        Query(description="추천 적합도·거리·이름 정렬"),
    ] = "RECOMMENDED",
) -> ListSuccessResponse[Place]:
    page_number = _recommendation_page_number(page_token)
    if filter_id is not None and filter_id != "PLAYER_PICK":
        try:
            TourFilterId(filter_id)
        except ValueError as exc:
            raise AppException(
                status_code=400,
                code="INVALID_RECOMMENDATION_FILTER",
                message="지원하지 않는 추천 장소 필터입니다.",
                details={"filterId": filter_id},
            ) from exc
    if keyword is not None and not keyword.strip():
        raise AppException(
            status_code=400,
            code="INVALID_RECOMMENDATION_KEYWORD",
            message="검색어에는 공백만 사용할 수 없습니다.",
        )
    candidates = await (
        ItineraryGenerationService().get_recommendation_candidates(
            user_id=user_id,
            trip_id=trip_id,
        )
    )
    if keyword is not None:
        normalized_keyword = keyword.strip().casefold()
        candidates = [
            place
            for place in candidates
            if normalized_keyword in place.name.casefold()
            or normalized_keyword in place.address.casefold()
        ]
    if filter_id is not None:
        candidates = [
            place
            for place in candidates
            if _matches_recommendation_filter(place, filter_id)
        ]
    if sort == "DISTANCE":
        candidates.sort(
            key=lambda place: (
                place.distance_meters is None,
                place.distance_meters or 0,
                place.name,
            )
        )
    elif sort == "NAME":
        candidates.sort(key=lambda place: place.name.casefold())

    start = (page_number - 1) * page_size
    page = candidates[start : start + page_size]
    next_page_token = (
        str(page_number + 1) if start + page_size < len(candidates) else None
    )
    return ListSuccessResponse(
        data=page,
        meta=ListMeta(
            count=len(page),
            next_page_token=next_page_token,
        ),
    )


@router.post(
    "/{tripId}/itineraries",
    response_model=SuccessResponse[ItineraryPlanResponse],
    status_code=status.HTTP_201_CREATED,
    summary="여행 일정 생성 및 저장",
    description=(
        "저장된 여행·경기·구장·선택 장소 정보를 조합하여 "
        "여행 일정을 생성하고 ACTIVE Plan으로 저장합니다. "
        "기존 일정 재생성 시 Anchor와 고정 장소는 유지하며, 고정되지 않은 "
        "기존 사용자 선택·자동 추천 장소는 이번 재생성 후보에서 제외합니다."
    ),
)
async def create_itinerary(
    trip_id: Annotated[
        str,
        Path(
            alias="tripId",
            description="여행 ID",
        ),
    ],
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> SuccessResponse[ItineraryPlanResponse]:
    service = ItineraryGenerationService()

    plan = await service.generate(
        user_id=user_id,
        trip_id=trip_id,
    )

    return SuccessResponse(
        data=to_itinerary_plan_response(plan)
    )


@router.post(
    "/{tripId}/plan/days/{date}/regenerate",
    response_model=SuccessResponse[ItineraryPlanResponse],
    summary="여행 일정 하루 재생성",
    description=(
        "같은 활성 Plan에서 선택한 날짜만 다시 생성합니다. "
        "고정 PLACE와 Anchor는 유지하고, 다른 날짜와 그 itemId는 변경하지 않습니다. "
        "선택한 날짜의 고정되지 않은 기존 사용자 선택·자동 추천 장소는 "
        "이번 재생성 후보에서 제외합니다."
    ),
)
async def regenerate_itinerary_day(
    trip_id: Annotated[str, Path(alias="tripId", description="여행 ID")],
    target_date: Annotated[
        date,
        Path(alias="date", description="한국시간 기준 재생성 날짜"),
    ],
    user_id: Annotated[str, Depends(get_current_active_user_id)],
) -> SuccessResponse[ItineraryPlanResponse]:
    plan = await ItineraryGenerationService().generate(
        user_id=user_id,
        trip_id=trip_id,
        target_date=target_date,
    )
    return SuccessResponse(data=to_itinerary_plan_response(plan))



@router.get(
    "/{tripId}/plan",
    response_model=SuccessResponse[ItineraryPlanResponse],
    summary="여행 일정 상세 조회",
    description=(
        "로그인 사용자가 소유한 여행의 "
        "현재 ACTIVE 일정 Plan을 조회합니다."
    ),
)
def get_active_itinerary_plan(
    trip_id: Annotated[
        str,
        Path(
            alias="tripId",
            description="여행 ID",
        ),
    ],
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> SuccessResponse[ItineraryPlanResponse]:
    service = ItineraryPlanService()

    plan = service.get_active_plan(
        user_id=user_id,
        trip_id=trip_id,
    )

    return SuccessResponse(
        data=to_itinerary_plan_response(plan)
    )


@router.delete(
    "/{tripId}/plan",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="여행 일정 삭제",
    description=(
        "로그인 사용자가 소유한 여행의 "
        "현재 ACTIVE 일정 Plan을 삭제합니다."
    ),
)
def delete_active_itinerary_plan(
    trip_id: Annotated[
        str,
        Path(
            alias="tripId",
            description="여행 ID",
        ),
    ],
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> Response:
    service = ItineraryPlanService()

    service.delete_active_plan(
        user_id=user_id,
        trip_id=trip_id,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )



@router.patch(
    "/{tripId}/plan/items/order",
    response_model=SuccessResponse[ItineraryPlanResponse],
    summary="여행 일정 장소 순서 변경",
    description=(
        "특정 날짜의 PLACE 항목 순서를 변경하고 "
        "이동시간과 방문시간을 다시 계산합니다."
    ),
)
async def reorder_itinerary_items(
    trip_id: Annotated[
        str,
        Path(
            alias="tripId",
            description="여행 ID",
        ),
    ],
    request: ItineraryPlanReorderRequest,
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> SuccessResponse[ItineraryPlanResponse]:
    service = ItineraryPlanService()

    plan = await service.reorder_items(
        user_id=user_id,
        trip_id=trip_id,
        request=request,
    )

    return SuccessResponse(
        data=to_itinerary_plan_response(plan)
    )



@router.delete(
    "/{tripId}/plan/items/{itemId}",
    response_model=SuccessResponse[ItineraryPlanResponse],
    summary="여행 일정 장소 삭제",
    description=(
        "현재 ACTIVE 일정에서 특정 PLACE 항목을 삭제하고 "
        "이동시간과 방문시간을 다시 계산합니다."
    ),
)
async def delete_itinerary_item(
    trip_id: Annotated[
        str,
        Path(
            alias="tripId",
            description="여행 ID",
        ),
    ],
    item_id: Annotated[
        str,
        Path(
            alias="itemId",
            description="삭제할 일정 항목 ID",
        ),
    ],
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> SuccessResponse[ItineraryPlanResponse]:
    service = ItineraryPlanService()

    plan = await service.delete_item(
        user_id=user_id,
        trip_id=trip_id,
        item_id=item_id,
    )

    return SuccessResponse(
        data=to_itinerary_plan_response(plan)
    )



@router.post(
    "/{tripId}/plan/items",
    response_model=SuccessResponse[ItineraryPlanResponse],
    summary="여행 일정 장소 추가",
    description=(
        "ACTIVE 일정에 장소를 추가하고 이동시간과 방문시간을 다시 계산합니다. "
        "date와 scheduledStartAt을 생략하면 첫째 날의 마지막 PLACE 뒤에 "
        "추가합니다. 반환되는 itemId는 위치나 순서를 뜻하지 않는 고유 "
        "식별자이므로 클라이언트는 문자열 형식을 해석하면 안 됩니다."
    ),
)
async def add_itinerary_item(
    trip_id: Annotated[
        str,
        Path(
            alias="tripId",
            description="여행 ID",
        ),
    ],
    request: ItineraryPlanAddItemRequest,
    user_id: Annotated[
        str,
        Depends(get_current_active_user_id),
    ],
) -> SuccessResponse[ItineraryPlanResponse]:
    service = ItineraryPlanService()

    plan = await service.add_item(
        user_id=user_id,
        trip_id=trip_id,
        request=request,
    )

    return SuccessResponse(
        data=to_itinerary_plan_response(plan)
    )


@router.patch(
    "/{tripId}/plan/items/{itemId}/fixed",
    response_model=SuccessResponse[ItineraryPlanResponse],
    summary="여행 일정 장소 고정 여부 변경",
)
async def update_itinerary_item_fixed(
    trip_id: Annotated[str, Path(alias="tripId")],
    item_id: Annotated[str, Path(alias="itemId")],
    request: ItineraryPlanFixedRequest,
    user_id: Annotated[str, Depends(get_current_active_user_id)],
) -> SuccessResponse[ItineraryPlanResponse]:
    plan = await ItineraryPlanService().update_item_fixed(
        user_id=user_id,
        trip_id=trip_id,
        item_id=item_id,
        request=request,
    )
    return SuccessResponse(data=to_itinerary_plan_response(plan))


@router.patch(
    "/{tripId}/plan/items/{itemId}/time",
    response_model=SuccessResponse[ItineraryPlanResponse],
    summary="여행 일정 장소 시작시간·날짜 변경",
    description=(
        "PLACE 유형의 시작시간을 변경합니다. "
        "scheduledStartAt의 날짜가 현재 날짜와 다르면 해당 PLACE를 "
        "대상 날짜의 일정으로 이동하고 출발 날짜와 대상 날짜의 "
        "이동정보를 다시 계산합니다. "
        "ARRIVAL_POINT, DEPARTURE_POINT, STADIUM, ACCOMMODATION "
        "Anchor는 이 API에서 변경할 수 없습니다."
    ),
)
async def update_itinerary_item_time(
    trip_id: Annotated[str, Path(alias="tripId", description="여행 ID")],
    item_id: Annotated[
        str,
        Path(
            alias="itemId",
            description="시간 또는 날짜를 변경할 PLACE 유형 Item ID",
        ),
    ],
    request: ItineraryPlanTimeUpdateRequest,
    user_id: Annotated[str, Depends(get_current_active_user_id)],
) -> SuccessResponse[ItineraryPlanResponse]:
    plan = await ItineraryPlanService().update_item_time(
        user_id=user_id,
        trip_id=trip_id,
        item_id=item_id,
        request=request,
    )
    return SuccessResponse(data=to_itinerary_plan_response(plan))

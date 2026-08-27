from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Header,
    Path,
    Response,
    status,
)

from app.api.dependencies.auth import get_current_active_user_id
from app.api.openapi_responses import TRIP_ERROR_RESPONSES
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


router = APIRouter(
    prefix="/trips",
    responses=TRIP_ERROR_RESPONSES,
)


def to_summary_response(
    trip: TripRecord,
) -> TripSummaryResponse:
    """TripRecord를 외부 공개용 요약 응답으로 변환합니다."""

    return TripSummaryResponse(
        trip_id=trip.trip_id,
        game_id=trip.game_id,
        title=trip.title,
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
        status=trip.status,
        trip_start_at=trip.trip_start_at,
        trip_end_at=trip.trip_end_at,
        created_at=trip.created_at,
        arrival_point=trip.arrival_point,
        departure_point=trip.departure_point,
        accommodation=trip.accommodation,
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
    description="로그인 사용자가 소유한 여행 목록을 조회합니다.",
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



@router.post(
    "/{tripId}/itineraries",
    response_model=SuccessResponse[ItineraryPlanResponse],
    status_code=status.HTTP_201_CREATED,
    summary="여행 일정 생성 및 저장",
    description=(
        "저장된 여행·경기·구장·선택 장소 정보를 조합하여 "
        "여행 일정을 생성하고 ACTIVE Plan으로 저장합니다."
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
    summary="여행 일정 장소 시작시간 변경",
    description=(
        "PLACE 유형의 itemId만 변경할 수 있습니다. "
        "ARRIVAL_POINT, DEPARTURE_POINT, STADIUM, ACCOMMODATION "
        "Anchor의 시간은 여행·경기·숙소 기본정보를 수정한 뒤 "
        "일정을 재생성하여 변경합니다."
    ),
)
async def update_itinerary_item_time(
    trip_id: Annotated[str, Path(alias="tripId", description="여행 ID")],
    item_id: Annotated[
        str,
        Path(alias="itemId", description="시간을 변경할 PLACE 유형 Item ID"),
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

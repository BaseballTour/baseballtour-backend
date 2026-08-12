from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Path,
    Response,
    status,
)

from app.api.dependencies.auth import get_current_user_id
from app.schemas.place_selection import (
    PlaceSelectionCreateRequest,
    PlaceSelectionRecord,
    PlaceSelectionResponse,
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
from app.services.place_selection_service import (
    PlaceSelectionService,
)
from app.services.trip_service import TripService


router = APIRouter(
    prefix="/trips",
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
        Depends(get_current_user_id),
    ],
) -> SuccessResponse[TripSummaryResponse]:
    service = TripService()

    trip = service.create_trip(
        user_id=user_id,
        request=request,
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
        Depends(get_current_user_id),
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
        Depends(get_current_user_id),
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
        Depends(get_current_user_id),
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
        Depends(get_current_user_id),
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
        Depends(get_current_user_id),
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
        Depends(get_current_user_id),
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
        Depends(get_current_user_id),
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

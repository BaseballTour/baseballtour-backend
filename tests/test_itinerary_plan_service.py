from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.exceptions import AppException
from app.schemas.itinerary_plan import (
    ItineraryPlanAddItemRequest,
    ItineraryPlanFixedRequest,
    ItineraryPlanRecord,
    ItineraryPlanReorderRequest,
    ItineraryPlanTimeUpdateRequest,
    ItineraryPlanStatus,
)
from app.schemas.trip import TripRecord, TripStatus
from app.services.itinerary_plan_service import (
    ItineraryPlanService,
)


USER_ID = "firebase-user-123"
TRIP_ID = "trip_001"
PLAN_ID = "plan_001"

NOW = datetime(
    2026,
    8,
    12,
    14,
    0,
    tzinfo=timezone.utc,
)


def make_trip(
    *,
    user_id: str = USER_ID,
    active_plan_id: str | None = PLAN_ID,
    trip_status: TripStatus = TripStatus.GENERATED,
) -> TripRecord:
    return TripRecord(
        trip_id=TRIP_ID,
        user_id=user_id,
        game_id="game_001",
        title="부산 직관 여행",
        trip_start_at="2026-08-15T12:00:00+09:00",
        trip_end_at="2026-08-15T23:00:00+09:00",
        arrival_point={
            "name": "부산역",
            "latitude": 35.1151,
            "longitude": 129.0414,
        },
        departure_point={
            "name": "부산역",
            "latitude": 35.1151,
            "longitude": 129.0414,
        },
        accommodation=None,
        status=trip_status,
        active_plan_id=active_plan_id,
        created_at=NOW,
        updated_at=NOW,
    )


def make_plan(
    *,
    user_id: str = USER_ID,
    trip_id: str = TRIP_ID,
) -> ItineraryPlanRecord:
    return ItineraryPlanRecord(
        plan_id=PLAN_ID,
        trip_id=trip_id,
        user_id=user_id,
        status=ItineraryPlanStatus.ACTIVE,
        algorithm_version="greedy-anchor-v0.1",
        total_travel_minutes=0,
        days=[],
        excluded_places=[],
        created_at=NOW,
        updated_at=NOW,
    )


def make_service(
    *,
    trip=None,
    plan=None,
):
    trip_repository = Mock()
    trip_repository.get_by_id.return_value = (
        trip if trip is not None else make_trip()
    )

    plan_repository = Mock()
    plan_repository.get_by_id.return_value = (
        plan if plan is not None else make_plan()
    )

    service = ItineraryPlanService(
        trip_repository=trip_repository,
        itinerary_plan_repository=plan_repository,
    )

    return service, trip_repository, plan_repository


def test_get_active_plan_returns_plan() -> None:
    service, _, plan_repository = make_service()

    result = service.get_active_plan(
        user_id=USER_ID,
        trip_id=TRIP_ID,
    )

    assert result.plan_id == PLAN_ID
    assert result.trip_id == TRIP_ID

    plan_repository.get_by_id.assert_called_once_with(
        PLAN_ID
    )


def test_get_active_plan_rejects_missing_trip() -> None:
    service, trip_repository, _ = make_service()
    trip_repository.get_by_id.return_value = None

    with pytest.raises(AppException) as captured:
        service.get_active_plan(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.status_code == 404
    assert captured.value.code == "TRIP_NOT_FOUND"


def test_get_active_plan_rejects_other_user() -> None:
    service, _, _ = make_service(
        trip=make_trip(
            user_id="another-user",
        )
    )

    with pytest.raises(AppException) as captured:
        service.get_active_plan(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.status_code == 403
    assert captured.value.code == "TRIP_ACCESS_DENIED"


def test_get_active_plan_rejects_missing_active_plan_id() -> None:
    service, _, plan_repository = make_service(
        trip=make_trip(
            active_plan_id=None,
            trip_status=TripStatus.PLANNING,
        )
    )

    with pytest.raises(AppException) as captured:
        service.get_active_plan(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.status_code == 404
    assert captured.value.code == (
        "ITINERARY_PLAN_NOT_FOUND"
    )

    plan_repository.get_by_id.assert_not_called()


def test_get_active_plan_rejects_missing_plan_document() -> None:
    service, _, plan_repository = make_service()
    plan_repository.get_by_id.return_value = None

    with pytest.raises(AppException) as captured:
        service.get_active_plan(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.code == (
        "ITINERARY_PLAN_NOT_FOUND"
    )


def test_delete_active_plan_calls_repository() -> None:
    service, _, plan_repository = make_service()

    service.delete_active_plan(
        user_id=USER_ID,
        trip_id=TRIP_ID,
    )

    plan_repository.delete_active_plan.assert_called_once()

    arguments = (
        plan_repository
        .delete_active_plan
        .call_args.kwargs
    )

    assert arguments["trip_id"] == TRIP_ID
    assert arguments["plan_id"] == PLAN_ID
    assert arguments["updated_at"].tzinfo is not None


def test_delete_active_plan_rejects_generation_in_progress() -> None:
    service, _, plan_repository = make_service(
        trip=make_trip(
            trip_status=TripStatus.GENERATING,
        )
    )

    with pytest.raises(AppException) as captured:
        service.delete_active_plan(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.status_code == 409
    assert captured.value.code == (
        "TRIP_GENERATION_IN_PROGRESS"
    )

    plan_repository.delete_active_plan.assert_not_called()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def make_editable_plan() -> ItineraryPlanRecord:
    return ItineraryPlanRecord(
        plan_id=PLAN_ID,
        trip_id=TRIP_ID,
        user_id=USER_ID,
        status=ItineraryPlanStatus.ACTIVE,
        algorithm_version="greedy-anchor-v0.1",
        total_travel_minutes=0,
        days=[
            {
                "date": "2026-08-15",
                "dayType": "ARRIVAL_DAY",
                "items": [
                    {
                        "itemId": "arrival",
                        "type": "ARRIVAL_POINT",
                        "sequence": 1,
                        "name": "부산역",
                        "address": "부산역",
                        "latitude": 35.1151,
                        "longitude": 129.0414,
                        "scheduledStartAt": (
                            "2026-08-15T12:00:00+09:00"
                        ),
                        "scheduledEndAt": (
                            "2026-08-15T12:20:00+09:00"
                        ),
                        "travelMinutesFromPrevious": 0,
                        "isRequired": True,
                    },
                    {
                        "itemId": "item_a",
                        "type": "PLACE",
                        "sequence": 2,
                        "placeId": "tour_a",
                        "name": "장소 A",
                        "address": "장소 A",
                        "latitude": 35.12,
                        "longitude": 129.05,
                        "scheduledStartAt": (
                            "2026-08-15T13:00:00+09:00"
                        ),
                        "scheduledEndAt": (
                            "2026-08-15T14:00:00+09:00"
                        ),
                        "travelMinutesFromPrevious": 0,
                        "isRequired": True,
                    },
                    {
                        "itemId": "item_b",
                        "type": "PLACE",
                        "sequence": 3,
                        "placeId": "tour_b",
                        "name": "장소 B",
                        "address": "장소 B",
                        "latitude": 35.13,
                        "longitude": 129.06,
                        "scheduledStartAt": (
                            "2026-08-15T15:00:00+09:00"
                        ),
                        "scheduledEndAt": (
                            "2026-08-15T16:00:00+09:00"
                        ),
                        "travelMinutesFromPrevious": 0,
                        "isRequired": True,
                    },
                ],
            }
        ],
        excluded_places=[],
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.mark.anyio
async def test_update_item_fixed_persists_flag() -> None:
    trip = make_trip()
    plan = make_editable_plan()
    trip_repository = Mock()
    trip_repository.get_by_id.return_value = trip
    plan_repository = Mock()
    plan_repository.get_by_id.return_value = plan
    plan_repository.update_schedule.side_effect = lambda **kwargs: plan.model_copy(
        update={"days": kwargs["days"]}
    )
    service = ItineraryPlanService(
        trip_repository=trip_repository,
        itinerary_plan_repository=plan_repository,
    )

    result = await service.update_item_fixed(
        user_id=USER_ID,
        trip_id=TRIP_ID,
        item_id="item_a",
        request=ItineraryPlanFixedRequest(is_fixed=True),
    )

    assert result.days[0].items[1].is_fixed is True


@pytest.mark.anyio
async def test_update_item_time_keeps_manual_times_and_recalculates_travel() -> None:
    trip = make_trip()
    plan = make_editable_plan()
    trip_repository = Mock()
    trip_repository.get_by_id.return_value = trip
    plan_repository = Mock()
    plan_repository.get_by_id.return_value = plan
    plan_repository.update_schedule.side_effect = lambda **kwargs: plan.model_copy(
        update={"days": kwargs["days"]}
    )

    async def provider(*args) -> int:
        return 10

    service = ItineraryPlanService(
        trip_repository=trip_repository,
        itinerary_plan_repository=plan_repository,
        travel_time_provider=provider,
    )
    result = await service.update_item_time(
        user_id=USER_ID,
        trip_id=TRIP_ID,
        item_id="item_a",
        request=ItineraryPlanTimeUpdateRequest(
            scheduled_start_at="2026-08-15T14:00:00+09:00"
        ),
    )

    items = result.days[0].items
    assert items[1].scheduled_start_at.hour == 14
    assert items[1].is_fixed is True
    assert items[1].travel_minutes_from_previous == 10
    assert items[2].scheduled_start_at.hour == 15
    assert items[2].scheduled_start_at.minute == 0
    assert items[2].travel_minutes_from_previous == 10


@pytest.mark.anyio
async def test_update_item_time_rejects_anchor_item_with_clear_error() -> None:
    trip = make_trip()
    plan = make_editable_plan()
    trip_repository = Mock()
    trip_repository.get_by_id.return_value = trip
    plan_repository = Mock()
    plan_repository.get_by_id.return_value = plan
    service = ItineraryPlanService(
        trip_repository=trip_repository,
        itinerary_plan_repository=plan_repository,
    )

    with pytest.raises(AppException) as captured:
        await service.update_item_time(
            user_id=USER_ID,
            trip_id=TRIP_ID,
            item_id="arrival",
            request=ItineraryPlanTimeUpdateRequest(
                scheduled_start_at="2026-08-15T13:00:00+09:00"
            ),
        )

    assert captured.value.status_code == 400
    assert captured.value.code == "ITINERARY_ANCHOR_NOT_EDITABLE"
    assert captured.value.details == {"itemType": "ARRIVAL_POINT"}
    plan_repository.update_schedule.assert_not_called()


@pytest.mark.anyio
async def test_update_item_time_can_move_place_to_another_plan_day() -> None:
    trip = make_trip().model_copy(
        update={"trip_end_at": "2026-08-16T23:00:00+09:00"}
    )
    plan = make_editable_plan()
    second_day = {
        "date": "2026-08-16",
        "dayType": "DEPARTURE_DAY",
        "items": [],
    }
    plan = ItineraryPlanRecord.model_validate(
        {
            **plan.model_dump(by_alias=False),
            "days": [plan.days[0], second_day],
        }
    )
    trip_repository = Mock()
    trip_repository.get_by_id.return_value = trip
    plan_repository = Mock()
    plan_repository.get_by_id.return_value = plan
    plan_repository.update_schedule.side_effect = lambda **kwargs: plan.model_copy(
        update={"days": kwargs["days"]}
    )

    async def provider(*args) -> int:
        return 12

    service = ItineraryPlanService(
        trip_repository=trip_repository,
        itinerary_plan_repository=plan_repository,
        travel_time_provider=provider,
    )
    result = await service.update_item_time(
        user_id=USER_ID,
        trip_id=TRIP_ID,
        item_id="item_a",
        request=ItineraryPlanTimeUpdateRequest(
            scheduled_start_at="2026-08-16T23:30:00+09:00"
        ),
    )

    assert [item.item_id for item in result.days[0].items] == [
        "arrival",
        "item_b",
    ]
    moved = result.days[1].items[0]
    assert moved.item_id == "item_a"
    assert moved.scheduled_start_at.isoformat() == "2026-08-16T23:30:00+09:00"
    assert moved.is_fixed is True
    assert moved.travel_minutes_from_previous == 12


@pytest.mark.anyio
async def test_reorder_items_updates_plan() -> None:
    trip = make_trip()
    plan = make_editable_plan()

    trip_repository = Mock()
    trip_repository.get_by_id.return_value = trip

    plan_repository = Mock()
    plan_repository.get_by_id.return_value = plan

    plan_repository.update_schedule.side_effect = (
        lambda **kwargs: plan.model_copy(
            update={
                "days": kwargs["days"],
                "total_travel_minutes": (
                    kwargs["total_travel_minutes"]
                ),
                "updated_at": kwargs["updated_at"],
            }
        )
    )

    async def provider(
        origin_longitude,
        origin_latitude,
        destination_longitude,
        destination_latitude,
    ) -> int:
        return 10

    service = ItineraryPlanService(
        trip_repository=trip_repository,
        itinerary_plan_repository=plan_repository,
        travel_time_provider=provider,
    )

    request = ItineraryPlanReorderRequest(
        date="2026-08-15",
        item_ids=[
            "item_b",
            "item_a",
        ],
    )

    result = await service.reorder_items(
        user_id=USER_ID,
        trip_id=TRIP_ID,
        request=request,
    )

    items = result.days[0].items

    assert [
        item.item_id
        for item in items
    ] == [
        "arrival",
        "item_b",
        "item_a",
    ]

    assert [
        item.sequence
        for item in items
    ] == [
        1,
        2,
        3,
    ]

    assert items[1].travel_minutes_from_previous == 10
    assert items[2].travel_minutes_from_previous == 10

    assert result.total_travel_minutes == 20

    plan_repository.update_schedule.assert_called_once()


@pytest.mark.anyio
async def test_reorder_items_rejects_unknown_day() -> None:
    trip_repository = Mock()
    trip_repository.get_by_id.return_value = make_trip()

    plan_repository = Mock()
    plan_repository.get_by_id.return_value = (
        make_editable_plan()
    )

    service = ItineraryPlanService(
        trip_repository=trip_repository,
        itinerary_plan_repository=plan_repository,
        travel_time_provider=None,
    )

    request = ItineraryPlanReorderRequest(
        date="2026-08-16",
        item_ids=[
            "item_b",
            "item_a",
        ],
    )

    with pytest.raises(AppException) as captured:
        await service.reorder_items(
            user_id=USER_ID,
            trip_id=TRIP_ID,
            request=request,
        )

    assert captured.value.status_code == 404
    assert captured.value.code == (
        "ITINERARY_DAY_NOT_FOUND"
    )

    plan_repository.update_schedule.assert_not_called()


def test_second_day_start_uses_korea_timezone_after_firestore_utc() -> None:
    original = make_trip()
    trip = original.model_copy(
        update={
            "trip_start_at": original.trip_start_at.astimezone(
                timezone.utc
            )
        }
    )
    service, _, _ = make_service(trip=trip)

    _, _, _, day_start = service._resolve_day_start(
        trip=trip,
        target_date=date(2026, 8, 16),
    )

    assert day_start.isoformat() == "2026-08-16T09:00:00+09:00"


@pytest.mark.anyio
async def test_reorder_items_rejects_invalid_item_ids() -> None:
    trip_repository = Mock()
    trip_repository.get_by_id.return_value = make_trip()

    plan_repository = Mock()
    plan_repository.get_by_id.return_value = (
        make_editable_plan()
    )

    service = ItineraryPlanService(
        trip_repository=trip_repository,
        itinerary_plan_repository=plan_repository,
        travel_time_provider=None,
    )

    request = ItineraryPlanReorderRequest(
        date="2026-08-15",
        item_ids=[
            "item_a",
        ],
    )

    with pytest.raises(AppException) as captured:
        await service.reorder_items(
            user_id=USER_ID,
            trip_id=TRIP_ID,
            request=request,
        )

    assert captured.value.status_code == 400
    assert captured.value.code == (
        "ITINERARY_EDIT_INVALID"
    )

    plan_repository.update_schedule.assert_not_called()


@pytest.mark.anyio
async def test_delete_item_removes_place_and_updates_plan() -> None:
    trip = make_trip()
    plan = make_editable_plan()

    trip_repository = Mock()
    trip_repository.get_by_id.return_value = trip

    plan_repository = Mock()
    plan_repository.get_by_id.return_value = plan

    plan_repository.update_schedule.side_effect = (
        lambda **kwargs: plan.model_copy(
            update={
                "days": kwargs["days"],
                "total_travel_minutes": (
                    kwargs["total_travel_minutes"]
                ),
                "updated_at": kwargs["updated_at"],
            }
        )
    )

    async def provider(
        origin_longitude,
        origin_latitude,
        destination_longitude,
        destination_latitude,
    ) -> int:
        return 10

    service = ItineraryPlanService(
        trip_repository=trip_repository,
        itinerary_plan_repository=plan_repository,
        travel_time_provider=provider,
    )

    result = await service.delete_item(
        user_id=USER_ID,
        trip_id=TRIP_ID,
        item_id="item_a",
    )

    items = result.days[0].items

    assert [
        item.item_id
        for item in items
    ] == [
        "arrival",
        "item_b",
    ]

    assert [
        item.sequence
        for item in items
    ] == [
        1,
        2,
    ]

    assert items[1].travel_minutes_from_previous == 10
    assert result.total_travel_minutes == 10

    plan_repository.update_schedule.assert_called_once()


@pytest.mark.anyio
async def test_delete_item_rejects_anchor() -> None:
    trip_repository = Mock()
    trip_repository.get_by_id.return_value = make_trip()

    plan_repository = Mock()
    plan_repository.get_by_id.return_value = (
        make_editable_plan()
    )

    service = ItineraryPlanService(
        trip_repository=trip_repository,
        itinerary_plan_repository=plan_repository,
        travel_time_provider=None,
    )

    with pytest.raises(AppException) as captured:
        await service.delete_item(
            user_id=USER_ID,
            trip_id=TRIP_ID,
            item_id="arrival",
        )

    assert captured.value.status_code == 400
    assert captured.value.code == (
        "ITINERARY_EDIT_INVALID"
    )

    plan_repository.update_schedule.assert_not_called()


@pytest.mark.anyio
async def test_delete_item_rejects_unknown_item() -> None:
    trip_repository = Mock()
    trip_repository.get_by_id.return_value = make_trip()

    plan_repository = Mock()
    plan_repository.get_by_id.return_value = (
        make_editable_plan()
    )

    service = ItineraryPlanService(
        trip_repository=trip_repository,
        itinerary_plan_repository=plan_repository,
        travel_time_provider=None,
    )

    with pytest.raises(AppException) as captured:
        await service.delete_item(
            user_id=USER_ID,
            trip_id=TRIP_ID,
            item_id="unknown_item",
        )

    assert captured.value.status_code == 404
    assert captured.value.code == (
        "ITINERARY_ITEM_NOT_FOUND"
    )

    plan_repository.update_schedule.assert_not_called()


@pytest.mark.anyio
async def test_add_item_adds_place_and_updates_plan() -> None:
    trip = make_trip()
    plan = make_editable_plan()

    trip_repository = Mock()
    trip_repository.get_by_id.return_value = trip

    plan_repository = Mock()
    plan_repository.get_by_id.return_value = plan

    plan_repository.update_schedule.side_effect = (
        lambda **kwargs: plan.model_copy(
            update={
                "days": kwargs["days"],
                "total_travel_minutes": (
                    kwargs["total_travel_minutes"]
                ),
                "updated_at": kwargs["updated_at"],
            }
        )
    )

    place_adapter = Mock()
    place_adapter.get_place_detail = AsyncMock(
        return_value=SimpleNamespace(
            place_id="tour_123456",
            name="새 장소",
            address="부산 새 장소",
            latitude=35.14,
            longitude=129.07,
            default_stay_minutes=60,
        )
    )

    async def provider(
        origin_longitude,
        origin_latitude,
        destination_longitude,
        destination_latitude,
    ) -> int:
        return 10

    service = ItineraryPlanService(
        trip_repository=trip_repository,
        itinerary_plan_repository=plan_repository,
        travel_time_provider=provider,
        place_adapter=place_adapter,
    )

    request = ItineraryPlanAddItemRequest(
        date="2026-08-15",
        place_id="tour_123456",
        is_required=True,
    )

    result = await service.add_item(
        user_id=USER_ID,
        trip_id=TRIP_ID,
        request=request,
    )

    items = result.days[0].items

    assert [
        item.place_id
        for item in items
        if item.place_id is not None
    ] == [
        "tour_a",
        "tour_b",
        "tour_123456",
    ]

    added = next(
        item
        for item in items
        if item.place_id == "tour_123456"
    )

    assert added.item_id.startswith("item_")
    assert added.sequence == 4
    assert added.is_required is True
    assert added.travel_minutes_from_previous == 10

    assert result.total_travel_minutes == 30

    place_adapter.get_place_detail.assert_awaited_once_with(
        "123456"
    )

    plan_repository.update_schedule.assert_called_once()


@pytest.mark.anyio
async def test_add_item_rejects_invalid_place_id() -> None:
    trip_repository = Mock()
    trip_repository.get_by_id.return_value = make_trip()

    plan_repository = Mock()
    plan_repository.get_by_id.return_value = (
        make_editable_plan()
    )

    place_adapter = Mock()
    place_adapter.get_place_detail = AsyncMock()

    service = ItineraryPlanService(
        trip_repository=trip_repository,
        itinerary_plan_repository=plan_repository,
        travel_time_provider=None,
        place_adapter=place_adapter,
    )

    request = ItineraryPlanAddItemRequest(
        date="2026-08-15",
        place_id="place_123456",
    )

    with pytest.raises(AppException) as captured:
        await service.add_item(
            user_id=USER_ID,
            trip_id=TRIP_ID,
            request=request,
        )

    assert captured.value.status_code == 400
    assert captured.value.code == (
        "ITINERARY_PLACE_ID_INVALID"
    )

    place_adapter.get_place_detail.assert_not_awaited()
    plan_repository.update_schedule.assert_not_called()


@pytest.mark.anyio
async def test_add_item_rejects_duplicate_place() -> None:
    trip_repository = Mock()
    trip_repository.get_by_id.return_value = make_trip()

    plan_repository = Mock()
    plan_repository.get_by_id.return_value = (
        make_editable_plan()
    )

    place_adapter = Mock()
    place_adapter.get_place_detail = AsyncMock()

    service = ItineraryPlanService(
        trip_repository=trip_repository,
        itinerary_plan_repository=plan_repository,
        travel_time_provider=None,
        place_adapter=place_adapter,
    )

    request = ItineraryPlanAddItemRequest(
        date="2026-08-15",
        place_id="tour_a",
    )

    with pytest.raises(AppException) as captured:
        await service.add_item(
            user_id=USER_ID,
            trip_id=TRIP_ID,
            request=request,
        )

    assert captured.value.status_code == 409
    assert captured.value.code == (
        "ITINERARY_PLACE_ALREADY_EXISTS"
    )

    place_adapter.get_place_detail.assert_not_awaited()
    plan_repository.update_schedule.assert_not_called()


@pytest.mark.anyio
async def test_add_item_rejects_missing_place() -> None:
    trip_repository = Mock()
    trip_repository.get_by_id.return_value = make_trip()

    plan_repository = Mock()
    plan_repository.get_by_id.return_value = (
        make_editable_plan()
    )

    place_adapter = Mock()
    place_adapter.get_place_detail = AsyncMock(
        side_effect=ValueError(
            "place not found"
        )
    )

    service = ItineraryPlanService(
        trip_repository=trip_repository,
        itinerary_plan_repository=plan_repository,
        travel_time_provider=None,
        place_adapter=place_adapter,
    )

    request = ItineraryPlanAddItemRequest(
        date="2026-08-15",
        place_id="tour_999999",
    )

    with pytest.raises(AppException) as captured:
        await service.add_item(
            user_id=USER_ID,
            trip_id=TRIP_ID,
            request=request,
        )

    assert captured.value.status_code == 404
    assert captured.value.code == (
        "ITINERARY_PLACE_NOT_FOUND"
    )

    plan_repository.update_schedule.assert_not_called()

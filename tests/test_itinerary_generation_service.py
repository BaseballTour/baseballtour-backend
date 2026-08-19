from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.exceptions import AppException
from app.models.itinerary import (
    ItineraryDay,
    ItineraryItem,
    ItineraryItemType,
    ItineraryResult,
)
from app.schemas.itinerary_plan import (
    ItineraryPlanRecord,
    ItineraryPlanStatus,
)
from app.schemas.trip import TripRecord, TripStatus
from app.services.itinerary_generation_service import (
    ItineraryGenerationService,
)


USER_ID = "firebase-user-123"
TRIP_ID = "trip_001"

START_AT = datetime.fromisoformat(
    "2026-08-15T12:00:00+09:00"
)
END_AT = datetime.fromisoformat(
    "2026-08-15T23:00:00+09:00"
)
GAME_AT = datetime.fromisoformat(
    "2026-08-15T18:00:00+09:00"
)

NOW = datetime(
    2026,
    8,
    12,
    14,
    0,
    tzinfo=timezone.utc,
)



@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def make_trip(
    *,
    user_id: str = USER_ID,
    trip_status: TripStatus = TripStatus.PLANNING,
    active_plan_id: str | None = None,
    arrival=True,
    departure=True,
) -> TripRecord:
    return TripRecord(
        trip_id=TRIP_ID,
        user_id=user_id,
        game_id="game_001",
        title="부산 직관 여행",
        trip_start_at=START_AT,
        trip_end_at=END_AT,
        arrival_point=(
            {
                "name": "부산역",
                "latitude": 35.1151,
                "longitude": 129.0414,
            }
            if arrival
            else None
        ),
        departure_point=(
            {
                "name": "부산역",
                "latitude": 35.1151,
                "longitude": 129.0414,
            }
            if departure
            else None
        ),
        accommodation=None,
        status=trip_status,
        active_plan_id=active_plan_id,
        created_at=NOW,
        updated_at=NOW,
    )


def make_game():
    return SimpleNamespace(
        game_id="game_001",
        stadium_id="sajik",
        game_start_at=GAME_AT,
    )


def make_stadium():
    return SimpleNamespace(
        stadium_id="sajik",
        name="사직야구장",
        address="부산광역시 동래구 사직로 45",
        latitude=35.194,
        longitude=129.0615,
    )


def make_result() -> ItineraryResult:
    item = ItineraryItem(
        type=ItineraryItemType.STADIUM,
        sequence=1,
        place_id="sajik",
        name="사직야구장",
        address="부산광역시 동래구 사직로 45",
        latitude=35.194,
        longitude=129.0615,
        scheduled_start_at=datetime.fromisoformat(
            "2026-08-15T17:20:00+09:00"
        ),
        scheduled_end_at=datetime.fromisoformat(
            "2026-08-15T21:00:00+09:00"
        ),
        travel_minutes_from_previous=0,
        travel_time_source=None,
        is_required=True,
    )

    return ItineraryResult(
        trip_id=TRIP_ID,
        algorithm_version="greedy-anchor-v0.1",
        total_travel_minutes=0,
        days=[
            ItineraryDay(
                date=START_AT.date(),
                day_type="GAME_DAY",
                items=[item],
            )
        ],
        excluded_places=[],
    )


def make_service(
    *,
    trip=None,
    game=None,
    stadium=None,
    selections=None,
    generator=None,
):
    trip_repository = Mock()
    trip_repository.get_by_id.return_value = (
        trip if trip is not None else make_trip()
    )
    trip_repository.update.side_effect = (
        lambda trip_id, updates: make_trip(
            trip_status=TripStatus(
                updates.get(
                    "status",
                    TripStatus.PLANNING.value,
                )
            )
        )
    )

    game_repository = Mock()
    game_repository.get_by_id.return_value = (
        game if game is not None else make_game()
    )

    stadium_repository = Mock()
    stadium_repository.get_by_id.return_value = (
        stadium
        if stadium is not None
        else make_stadium()
    )

    selection_repository = Mock()
    selection_repository.get_all.return_value = (
        selections if selections is not None else []
    )

    plan_repository = Mock()

    plan_repository.commit_generated_plan.side_effect = (
        lambda **kwargs: ItineraryPlanRecord(
            plan_id="plan_001",
            **kwargs["plan"].model_dump(),
        )
    )

    place_adapter = Mock()
    place_adapter.get_place_detail = AsyncMock()

    service = ItineraryGenerationService(
        trip_repository=trip_repository,
        game_repository=game_repository,
        stadium_repository=stadium_repository,
        place_selection_repository=selection_repository,
        itinerary_plan_repository=plan_repository,
        place_adapter=place_adapter,
        travel_time_provider=None,
        generator=generator or (lambda *_: make_result()),
    )

    return SimpleNamespace(
        service=service,
        trip_repository=trip_repository,
        game_repository=game_repository,
        stadium_repository=stadium_repository,
        selection_repository=selection_repository,
        plan_repository=plan_repository,
        place_adapter=place_adapter,
    )


@pytest.mark.anyio
async def test_generate_saves_active_plan() -> None:
    context = make_service()

    result = await context.service.generate(
        user_id=USER_ID,
        trip_id=TRIP_ID,
    )

    assert result.plan_id == "plan_001"
    assert result.status == ItineraryPlanStatus.ACTIVE
    assert result.days[0].items[0].item_id == "item_1_1"

    updates = context.trip_repository.update.call_args_list

    assert updates[0].args[1]["status"] == "GENERATING"

    context.plan_repository.commit_generated_plan.assert_called_once()

    arguments = (
        context.plan_repository
        .commit_generated_plan
        .call_args.kwargs
    )

    assert arguments["trip_id"] == TRIP_ID
    assert arguments["previous_plan_id"] is None
    assert arguments["plan"].trip_id == TRIP_ID
    assert arguments["plan"].user_id == USER_ID


@pytest.mark.anyio
async def test_generate_passes_previous_active_plan() -> None:
    context = make_service(
        trip=make_trip(
            trip_status=TripStatus.GENERATED,
            active_plan_id="plan_old",
        )
    )

    await context.service.generate(
        user_id=USER_ID,
        trip_id=TRIP_ID,
    )

    arguments = (
        context.plan_repository
        .commit_generated_plan
        .call_args.kwargs
    )

    assert arguments["previous_plan_id"] == "plan_old"


@pytest.mark.anyio
async def test_generate_rejects_missing_trip() -> None:
    context = make_service()
    context.trip_repository.get_by_id.return_value = None

    with pytest.raises(AppException) as captured:
        await context.service.generate(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.status_code == 404
    assert captured.value.code == "TRIP_NOT_FOUND"


@pytest.mark.anyio
async def test_generate_rejects_other_user_trip() -> None:
    context = make_service(
        trip=make_trip(
            user_id="another-user",
        )
    )

    with pytest.raises(AppException) as captured:
        await context.service.generate(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.status_code == 403
    assert captured.value.code == "TRIP_ACCESS_DENIED"


@pytest.mark.anyio
async def test_generate_rejects_generation_in_progress() -> None:
    context = make_service(
        trip=make_trip(
            trip_status=TripStatus.GENERATING,
        )
    )

    with pytest.raises(AppException) as captured:
        await context.service.generate(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.status_code == 409
    assert captured.value.code == (
        "TRIP_GENERATION_IN_PROGRESS"
    )

    context.trip_repository.update.assert_not_called()


@pytest.mark.anyio
async def test_generate_requires_arrival_and_departure() -> None:
    context = make_service(
        trip=make_trip(
            arrival=False,
            departure=False,
        )
    )

    with pytest.raises(AppException) as captured:
        await context.service.generate(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.status_code == 400
    assert captured.value.code == "TRIP_POINTS_REQUIRED"
    assert captured.value.details == {
        "missingFields": [
            "arrivalPoint",
            "departurePoint",
        ]
    }


@pytest.mark.anyio
async def test_generate_restores_status_when_game_missing() -> None:
    context = make_service()
    context.game_repository.get_by_id.return_value = None

    with pytest.raises(AppException) as captured:
        await context.service.generate(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.code == "GAME_NOT_FOUND"

    updates = context.trip_repository.update.call_args_list

    assert updates[0].args[1]["status"] == "GENERATING"
    assert updates[-1].args[1]["status"] == "PLANNING"


@pytest.mark.anyio
async def test_generate_restores_generated_status_on_regeneration_failure() -> None:
    context = make_service(
        trip=make_trip(
            trip_status=TripStatus.GENERATED,
            active_plan_id="plan_old",
        )
    )

    context.stadium_repository.get_by_id.return_value = None

    with pytest.raises(AppException) as captured:
        await context.service.generate(
            user_id=USER_ID,
            trip_id=TRIP_ID,
        )

    assert captured.value.code == "STADIUM_NOT_FOUND"

    updates = context.trip_repository.update.call_args_list

    assert updates[0].args[1]["status"] == "GENERATING"
    assert updates[-1].args[1]["status"] == "GENERATED"
